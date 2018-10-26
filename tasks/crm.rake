namespace :crm do
  # Last updated 2018-01-15
  REDMINE_GENERIC_USERS = [
    'Redmine Admin',
    'API Access',
    'Time Tracking',
  ]

  # Open Contracting Partnership
  # https://www.open-contracting.org/about/team/
  REDMINE_OCP_USERS_OCDS = [
    'Bernadine Fernz',
    'Carey Kluttz',
    'Hera Hussain',
    'James McKinney',
    'Karolis Granickas',
    'Lindsey Marchessault',
    'Nicolás Penagos',
  ]
  REDMINE_OCP_USERS = REDMINE_OCP_USERS_OCDS + [
    'Coby Jones',
    'David Selassie Opoku',
    'Gavin Hayman',
    'Georg Neumann',
    'Katherine Wikrent',
    'Kathrin Frauscher',
    'Marie Goumballa',
  ]

  # Open Data Services Co-operative Limited
  # http://opendataservices.coop
  REDMINE_ODS_USERS_OCDS = [
    'Charlie Pinder',
    'Duncan Dewhurst',
    'Matt Marshall',
    'Tim Williams',
  ]
  REDMINE_ODS_USERS_TECH = [
    'Amy Guy',
    'Ben Webb',
    'Bibiana Cristofol',
    'David Raznick',
    'David Spencer',
    'Jack Lord',
    'James Baster',
    'Rob Redpath',
    'Rory Scott',
    'Steven Flower',
  ]
  REDMINE_ODS_COORDINATOR = [
    'Rob Redpath',
  ]
  REDMINE_ODS_USERS = REDMINE_ODS_USERS_OCDS + REDMINE_ODS_USERS_TECH

  # Iniciativa Latinoamericana por los Datos Abiertos
  # https://idatosabiertos.org/acerca-de-nosotros/
  REDMINE_ILDA_USERS_OCDS = [
    'María Esther Cervantes',
    'Romina Fernández Valdez',
    'Yohanna Lisnichuk',
  ]
  REDMINE_ILDA_USERS = REDMINE_ILDA_USERS_OCDS + [
    'Fabrizio Scrollini',
    'Juan Pane',
  ]

  REDMINE_EXTERNAL_USERS = [
    'Rob Davidson',  # James McKinney
    'Ramon Olivas',  # Nicolás Penagos
  ]

  REDMINE_ALL_USERS = REDMINE_GENERIC_USERS + REDMINE_OCP_USERS + REDMINE_ODS_USERS + REDMINE_ILDA_USERS + REDMINE_EXTERNAL_USERS

  def crm_api_client
    @crm_api_client ||= begin
      client = Faraday.new
      client.basic_auth(ENV.fetch('username'), ENV.fetch('password'))
      client
    end
  end

  def crm_api_client_get(url)
    JSON.parse(crm_api_client.get("https://crm.open-contracting.org#{url}").body)
  end

  def csv_from_url(url, options={})
    CSV.parse(open(url).read, options.merge(headers: true))
  end

  # See https://www.redmineup.com/pages/help/crm/listing-contacts-api
  def contacts_from_crm(suffix='')
    offset = 0
    url = "/contacts.json?limit=100&offset=%d#{suffix}"

    contacts = []

    loop do
      data = crm_api_client_get(url % offset)
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

  desc 'Lists users not employed by the Open Contracting Partnership or its helpdesk teams'
  task :users do
    known_users = REDMINE_ALL_USERS

    # https://www.redmine.org/projects/redmine/wiki/Rest_Users
    users = crm_api_client_get("/users.json?limit=100")['users']

    names = users.map{ |user| "#{user['firstname']} #{user['lastname']}" }

    puts names - known_users

    difference = known_users - names
    if difference.any?
      puts "remove from tasks/crm.rake: #{difference.join(', ')}"
    end
  end

  desc 'Lists groups with missing or unexpected users'
  task :groups do
    groups = {
      # Open Contracting Partnership
      5 => [:exactly, REDMINE_OCP_USERS],
      # Open Data Services
      4 => [:exactly, REDMINE_ODS_USERS + ['API Access']],
      # Iniciativa Latinoamericana por los Datos Abiertos
      33 => [:exactly, REDMINE_ILDA_USERS],

      # Everyone excluding ODS Tech Team
      44 => [:exactly, REDMINE_OCP_USERS + REDMINE_ODS_USERS_OCDS + REDMINE_ILDA_USERS + REDMINE_ODS_COORDINATOR],
      # OCP Program Managers & Helpdesk Teams
      65 => [:exactly, REDMINE_OCP_USERS_OCDS + REDMINE_ODS_USERS_OCDS + REDMINE_ILDA_USERS_OCDS + REDMINE_ODS_COORDINATOR],

      # Helpdesk Teams
      43 => [:exactly, REDMINE_ODS_USERS_OCDS + REDMINE_ILDA_USERS_OCDS],
      # English Helpdesk Team
      66 => [:exactly, REDMINE_ODS_USERS_OCDS],
      # Partners and Consultants
      6 => [:exactly, REDMINE_EXTERNAL_USERS],
    }

    groups.each do |group_id, (modifier, known_users)|
      # https://www.redmine.org/projects/redmine/wiki/Rest_Groups
      group = crm_api_client_get("/groups/#{group_id}.json?include=users")['group']

      users = group['users'].map{ |user| user['name'] }

      case modifier
      when :exactly
        difference = users - known_users
        if difference.any?
          puts "https://crm.open-contracting.org/groups/#{group_id}/edit?tab=users: #{group['name']}: remove #{difference.join(', ')}"
        end

        difference = known_users - users
        if difference.any?
          puts "https://crm.open-contracting.org/groups/#{group_id}/edit?tab=users: #{group['name']}: add #{difference.join(', ')}"
        end
      when :only
        difference = users - known_users
        if difference.any?
          puts "https://crm.open-contracting.org/groups/#{group_id}/edit?tab=users: #{group['name']}: remove #{difference.join(', ')}"
        end
      when :except
        intersection = users & known_users
        if intersection.any?
          puts "https://crm.open-contracting.org/groups/#{group_id}/edit?tab=users: #{group['name']}: remove #{intersection.join(', ')}"
        end
      else
        raise "unexpected modifier #{modifier}"
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

    folders = {}
    q = "'0B5qzJROt-jZ0Ui1hSGlLdkxoY0E' in parents" # "1. Publishers" folder
    service.list_files(q: q).items.each do |file|
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
