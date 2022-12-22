namespace :crm do
  # Open Contracting Partnership
  # https://www.open-contracting.org/about/team/
  REDMINE_OCP_USERS = [
    # Data Team
    'Andidiong Okon',
    'Andrii Hazin',
    'Camila Salazar',
    'Félix Penna',
    'James McKinney',
    'Lindsey Marchessault',
    'Yohanna Lisnichuk',
    # Program Managers
    'Bernadine Fernz',
    'Carey Kluttz',
    'Edwin Muhumuza',
    'Guillermo Burr',
    'Karolis Granickas',
    'Mariana Lopez Fernandez',
    'Mariana San Martin',
    'Nanda Sihombing',
    'Oscar Hernandez',
    'Reilly Martin',
    'Sofía Garzón',
    'Viktor Nestulia',
    'Volodymyr Tarnay',
    # Others
    'Gavin Hayman',
    'Georg Neumann',
    'Kathrin Frauscher',
    'Kaye Sklar',
    'Kisha Bwenge',
    'Kristen Robinson',
    'Sophie Brown',
  ]

  REDMINE_EXTERNAL_USERS = []

  REDMINE_ALL_USERS = REDMINE_OCP_USERS + REDMINE_EXTERNAL_USERS

  def crm_api_client
    @crm_api_client ||= begin
      client = Faraday.new
      client.basic_auth(ENV.fetch('username'), ENV.fetch('password'))
      client
    end
  end

  def crm_api_client_get(url)
    response = crm_api_client.get("https://crm.open-contracting.org#{url}")
    if response.status != 200
      raise response.headers['status']
    end
    JSON.parse(response.body)
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

  desc 'Lists users not employed by the Open Contracting Partnership'
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
      65 => [:exactly, REDMINE_OCP_USERS],

      # Helpdesk Analysts
      43 => [:exactly, []],
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
