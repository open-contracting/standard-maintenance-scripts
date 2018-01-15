# See https://developers.google.com/drive/v2/web/quickstart/ruby
OOB_URI = 'urn:ietf:wg:oauth:2.0:oob'
APPLICATION_NAME = 'Drive API Ruby Quickstart'
CLIENT_SECRETS_PATH = 'client_secret.json'
CREDENTIALS_PATH = File.join(Dir.home, '.credentials', 'drive-ruby-quickstart.yaml')
SCOPE = Google::Apis::DriveV2::AUTH_DRIVE_METADATA_READONLY

namespace :crm do
  # See https://developers.google.com/drive/v2/web/quickstart/ruby
  def authorize
    FileUtils.mkdir_p(File.dirname(CREDENTIALS_PATH))

    client_id = Google::Auth::ClientId.from_file(CLIENT_SECRETS_PATH)
    token_store = Google::Auth::Stores::FileTokenStore.new(file: CREDENTIALS_PATH)
    authorizer = Google::Auth::UserAuthorizer.new(client_id, SCOPE, token_store)
    user_id = 'default'
    credentials = authorizer.get_credentials(user_id)

    if credentials.nil?
      url = authorizer.get_authorization_url(base_url: OOB_URI)
      puts 'Open the following URL in the browser and enter the resulting code after authorization'
      puts url
      code = gets
      credentials = authorizer.get_and_store_credentials_from_code(user_id: user_id, code: code, base_url: OOB_URI)
    end

    credentials
  end

  def crm_api_client
    @crm_api_client ||= begin
      client = Faraday.new
      client.basic_auth(ENV.fetch('username'), ENV.fetch('password'))
      client
    end
  end

  def csv_from_url(url, options={})
    CSV.parse(open(url).read, options.merge(headers: true))
  end

  # See https://www.redmineup.com/pages/help/crm/listing-contacts-api
  def contacts_from_crm(suffix='')
    offset = 0
    url = "https://crm.open-contracting.org/contacts.json?limit=100&offset=%d#{suffix}"

    contacts = []

    loop do
      data = JSON.parse(crm_api_client.get(url % offset).body)
      contacts += data['contacts']

      if contacts.size < data['total_count']
        print '.'
        offset += 100
      else
        puts
        return contacts
      end
    end
  end

  def contact_link(contact, suffix='')
    "http://crm.open-contracting.org/contacts/#{contact['id']}#{suffix}".ljust(45 + suffix.size)
  end

  def contact_error(contact, message, suffix='')
    puts "#{contact_link(contact, suffix)} #{message}"
  end

  desc 'Lists users not employed by the Open Contracting Partnership or its helpdesk teams'
  task :users do
    # Last updated 2018-01-15
    known_users = [
      'Redmine Admin',
      'API Access',

      # Open Contracting Partnership
      # https://www.open-contracting.org/about/team/
      'Carey Kluttz',
      'Gavin Hayman',
      'Georg Neumann',
      'Hera Hussain',
      'James McKinney',
      'Karolis Granickas',
      'Katherine Wikrent',
      'Kathrin Frauscher',
      'Lindsey Marchessault',
      'Leigh Manasco',
      'Marie Goumballa',

      # Open Data Services Co-op
      # http://opendataservices.coop
      'Bob Harper',
      'Ben Webb',
      'David Raznick',
      'David Spencer',
      'Duncan Dewhurst',
      'Eduardo Gomez',
      'Jack Lord',
      'Julija Hansen',
      'Rob Redpath',
      'Rory Scott',
      'Steven Flower',
      'Tim Davies',

      # Iniciativa Latinoamericana por los Datos Abiertos
      # https://idatosabiertos.org/acerca-de-nosotros/
      'Catalina Demidchuk',
      'Fabrizio Scrollini',
      'Juan Pane',
      'Oscar Montiel',
      'Yohanna Lisnichuk',
    ]

    users = JSON.parse(crm_api_client.get("https://crm.open-contracting.org/users.json?limit=100").body)['users']

    names = users.map{ |user| "#{user['firstname']} #{user['lastname']}" }

    puts names - known_users

    difference = known_users - names
    if difference.any?
      puts "remove from tasks/crm.rake: #{difference.join(', ')}"
    end
  end

  desc 'Prints the errors in contacts'
  task :check do
    contacts = contacts_from_crm

    companies = {}
    contacts.each do |contact|
      if contact['is_company']
        key = contact['first_name']
        if companies.key?(key)
          puts "unexpected collision on company name '#{key}'"
        else
          companies[key] = contact
        end
      end
    end

    address_components = ['country_code', 'region', 'city']

    disjoint_sets = {
      organization_types: Set.new([
        'academia',
        'civil society',
        'donor',
        'government agency',
        'private sector',
      ]),
      person_types: Set.new([ # optional
        'procurement expert',
        'staff',
        'translator',
      ]),
      geographic_levels: Set.new([
        'supranational',
        'national',
        'subnational',
        'local',
      ]),
      publication_stage: Set.new([ # optional
        'stage - commitment',
        'stage - in progress',
      ]),
    }

    contacts.each do |contact|
      is_company = contact['is_company']
      last_name = contact['last_name']
      company = contact['company']

      tags = Set.new(contact['tag_list'].map(&:downcase))

      groups = {}
      disjoint_sets.each do |key, group|
        groups[key] = tags.select{ |tag| disjoint_sets[key].include?(tag) }
        if groups[key].size > 1
          contact_error(contact, "remove one of #{groups[key].join(', ')}")
        end
      end

      expected_groups = []
      unexpected_tags = []
      expected_address_components = ['country_code']

      if is_company
        expected_groups << :organization_types
        unexpected_tags += groups[:person_types]

        if tags.include?('government agency')
          expected_groups << :geographic_levels
        elsif is_company
          unexpected_tags += groups[:geographic_levels] + groups[:publication_stage]
        end

        if tags.include?('subnational')
          expected_address_components << 'region'
        elsif tags.include?('local')
          expected_address_components += ['region', 'city']
        end

        if !last_name.empty?
          contact_error(contact, "remove 'Last name' value", '/edit')
        end
      else
        unexpected_tags += groups.values.flatten - groups[:person_types]

        if !company.empty? && !companies.key?(company) && company != 'Independent Consultant'
          contact_error(contact, "create company contact for '#{company}'")
        end

        if last_name.empty? || last_name == '-'
          contact_error(contact, "add 'Last name' value", '/edit')
        end
      end

      if !unexpected_tags.empty?
        message = "remove #{unexpected_tags.join(', ')}"
        if !is_company
          message << " or check 'Company' box"
        elsif !tags.include?('government agency')
          message << " or add 'government agency'"
        end
        contact_error(contact, message)
      end

      expected_groups.each do |key|
        if groups[key].empty?
          contact_error(contact, "add one of #{disjoint_sets[key].to_a.join(', ')}")
        end
      end

      empty_address_components = expected_address_components.select{ |key| contact['address'][key].empty? }
      if empty_address_components.any?
        contact_error(contact, "set #{empty_address_components.join(', ')} in 'Address' field", '/edit')
      end

      if tags.include?('support provider') && !company.empty?
        contact_error(contact, "remove 'support provider' from individual and add to company")
      end
    end
  end

  desc 'Prints the contacts with non-reactive support'
  task :statuses do
    contacts = contacts_from_crm

    sources = {
      'Catalytic support' => 'https://docs.google.com/document/d/1RLuHaczux67git5G8dN_nN3R-ffjjCCcKA1rX1lH0LI/edit',
      'Showcase and learning' => 'https://www.open-contracting.org/why-open-contracting/showcase-projects/',
    }

    statuses = {}
    contacts.each do |contact|
      value = contact['custom_fields'].find{ |custom_field| custom_field['id'] == 3 }['value']
      if !['Reactive support', ''].include?(value)
        statuses[value] ||= []
        statuses[value] << contact
      end
    end

    statuses.each do |value, contacts|
      puts "\n#{value}"
      if sources.key?(value)
        puts "Primary source: #{sources[value]}"
      end

      contacts.each_with_index do |contact, i|
        puts "#{'%2d' % (i + 1)}:  #{contact_link(contact, '/edit')}  #{contact['address']['country_code']}  #{contact['first_name']}"
      end
    end
  end

  desc 'Prints tab-separated values to paste into a contacts spreadsheet'
  task :dashboard do
    # Population data.
    url = 'https://raw.githubusercontent.com/datasets/population/master/data/population.csv'
    populations = csv_from_url(url).select{ |row| row.fetch('Year') == '2016' }

    # Country data.
    countries = {}
    url = 'https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv'
    csv_from_url(url).each do |row|
      countries[row.fetch('ISO3166-1-Alpha-3')] = row
    end

    # Google Drive data.
    service = Google::Apis::DriveV2::DriveService.new
    service.client_options.application_name = APPLICATION_NAME
    service.authorization = authorize

    folders = {}
    q = "'0B5qzJROt-jZ0Ui1hSGlLdkxoY0E' in parents" # "1. Publishers" folder
    service.list_files(q: q).each do |file|
      folders[file.title] = file
    end

    # CRM data.
    contacts = {}
    suffix = '&tags=government%%20agency' # TODO &tags=national
    contacts_from_crm(suffix).each do |contact|
      key = contact['address']['country_code']
      if contacts.key?(key)
        $stderr.puts "unexpected collision on country code '#{key}'"
      else
        contacts[key] = {
          'id' => contact['id'],
          'data_urls' => contact['custom_fields'].find{ |custom_field| custom_field['id'] == 2 }['value'],
        }
      end
    end

    # TODO Handle: non-national government agencies; multiple national government agencies.

    rows = []
    populations.each do |population|
      country_code = population.fetch('Country Code')
      country_name = population.fetch('Country Name')

      begin
        country = countries.fetch(country_code)
      rescue KeyError
        next # Not a country.
      end

      country_two_letter_code = country.fetch('ISO3166-1-Alpha-2')
      classifications = [country.fetch('Developed / Developing Countries')]

      [ 'Land Locked Developing Countries (LLDC)',
        'Least Developed Countries (LDC)',
        'Small Island Developing States (SIDS)',
      ].each do |key|
        value = country.fetch(key)
        case value
        when 'x'
          classifications << key
        when nil
          # Do nothing.
        else
          $stderr.puts "unexpected value #{value.inspect} in '#{key}' for #{country_code}"
        end
      end

      if folders.key?(country_name)
        drive_folder_url = folders.delete(country_name).alternate_link
      else
        drive_folder_url = nil
      end

      contact = contacts.delete(country_two_letter_code) || {}

      rows << {
        'Organization' => contact['first_name'],
        'Country name' => country_name,
        'Population' => population.fetch('Value'),
        'Continent code' => country.fetch('Continent'),
        'Country code' => country_two_letter_code,
        'Region name' => country.fetch('Sub-region Name'),
        'Currency code' => country.fetch('ISO4217-currency_alphabetic_code'),
        'Languages' => country.fetch('Languages'),
        'Classifications' => classifications.join("\n"),
        'Drive folder URL' => drive_folder_url,
        'Data URLs' => contact['data_urls'],
        'CRM contact URL' => "http://crm.open-contracting.org/contacts/#{contact['id']}",
      }
    end

    if folders.any?
      $stderr.puts "The following folders matched no country name:\n#{folders.keys.join("\n")}"
    end

    if contacts.any?
      $stderr.puts "The following contacts matched no country code:\n#{contacts.map{ |contact| contact_link(contact) }.join("\n")}"
    end

    headers = [
      'Organization',
      'Population',
      'Continent code',
      'Country code',
      'Region',
      'Currency code',
      'Languages',
      'Classifications',
    ]

    CSV($stdout, col_sep: "\t") do |csv|
      csv << headers

      rows.each do |row|
        csv << row.values
      end
    end
  end
end
