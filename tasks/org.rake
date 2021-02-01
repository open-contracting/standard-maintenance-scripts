namespace :org do
  # Last updated 2021-02-01
  MEMBERS = {
    'General' => [
      # Open Contracting Partnership
      # https://www.open-contracting.org/about/team/
      'jpmckinney', # James McKinney
      'lindseyam', # Lindsey Marchessault
      'yolile', # Yohanna Lisnichuk

      # Centro de Desarrollo Sostenible
      'aguilerapy', # Andrés Aguilera
      'nativaldezt', # Natalia Valdez

      # Open Data Services Co-operative Limited
      # http://opendataservices.coop
      'duncandewhurst', # Duncan Dewhurst
      'mrshll1001', # Matt Marshall
      'odscrachel', # Rachel Vint
      'pindec', # Charlie Pinder
      # Developers
      'bjwebb', # Ben Webb
      'kindly', # David Raznick
      'michaelwood', # Michael Wood
      'robredpath', # Rob Redpath
      'tim0th1', # Tim Williams
      # 'rhiaro', # Amy Guy
      # 'bibianac', # Bibiana Cristofol
      # 'idlemoor', # David Spencer
      # 'odscjames', # James Baster
      # 'scatteredink', # Jack Lord
      # 'rory09', # Rory Scott
    ],
    'Datlab' => [
      'jakubkrafka',
      'hrubyjan',
    ],
    'Health' => [
      # Transparency International
      'sean-darby',

      # Young Innovations
      'abhishekska',
      'anjesh',
      'anjilab',
      'bigyan',
      'bikramtuladhar',
      'duptitung',
      'kushalraj',
      'nirazanbasnet',
      'prashantsh',
      'rubinakarki',
      'simranthapa634',
      'sonikabaniya',
      'suhanapradhan',
      'suyojman',
    ],
    'Standard' => [
      'colinmaudry',
      'jachymhercher',
    ],
    'Servers' => [
      # Root access to specific servers
      'aguilerapy',
      'bjwebb',
      'bikramtuladhar',
      'kindly',
      'nativaldezt',

      # Dogsbody Technology Limited
      'dogsbody', # Dan Benton
      'dogsbody-ashley', # Ashley Holland
      'dogsbody-josh', # Josh Archer
      'jimacarter', # Jim Carter
      'robhooper', # Rob Hooper
    ]
  }

  ADMINS = [
    'jpmckinney',
    'yolile',
  ]

  desc 'Lists members that should be added or removed from the organization'
  task :members do
    expected = MEMBERS.values.flatten

    organizations.each do |organization|
      people = client.org_members(organization, per_page: 100) + client.org_invitations(organization)
      names = people.map{ |member| member.login.downcase }

      difference = names - expected
      if difference.any?
        puts "#{organization}: add to MEMBERS in tasks/org.rake: #{difference.join(', ')}"
      end

      # MEMBERS is based only on the membership of the open-contracting organization.
      if organization != 'open-contracting-extensions'
        difference = expected - names
        if difference.any?
          puts "#{organization}: remove from MEMBERS in tasks/org.rake: #{difference.join(', ')}"
        end
      end
    end
  end

  desc 'Lists owners that should be added or removed from the organization'
  task :owners do
    organizations.each do |organization|
      people = client.org_members(organization, role: 'admin', per_page: 100)
      names = people.map{ |member| member.login.downcase }

      difference = names - ADMINS
      if difference.any?
        puts "#{organization}: add to ADMINS in tasks/org.rake: #{difference.join(', ')}"
      end

      difference = ADMINS - names
      if difference.any?
        puts "#{organization}: remove from ADMINS in tasks/org.rake: #{difference.join(', ')}"
      end
    end
  end

  desc 'Removes admin access to specific repositories from non-admin members'
  task :collaborators do
    repos.each do |repo|
      repo.rels[:collaborators].get(query: {affiliation: 'direct'}).data.each do |collaborator|
        owner = repo.owner.login.downcase
        login = collaborator.login.downcase
        if collaborator.permissions.admin && !ADMINS.include?(login) # change role of repository creator
          client.remove_collaborator(repo.full_name, collaborator.login)
          puts "#{repo.html_url}/settings/access removed #{collaborator.login.bold}"
        elsif owner == 'open-contracting-extensions' && login == 'colinmaudry' # has access via org membership
          client.remove_collaborator(repo.full_name, collaborator.login)
          puts "#{repo.html_url}/settings/access removed #{collaborator.login.bold}"
        else
          puts "#{repo.html_url}/settings/access #{collaborator.login} has access"
        end
      end
    end
  end

  desc 'Lists members that should be added or removed from teams'
  task :team_members do
    client.org_teams('open-contracting').each do |team|
      names = client.team_members(team.id, per_page: 100).map{ |member| member.login.downcase }
      expected = MEMBERS.fetch(team.name)

      difference = names - expected
      if difference.any?
        puts "#{team.name}: add to MEMBERS['#{team.name}'] in tasks/org.rake: #{difference.join(', ')}"
      end

      difference = expected - names
      if difference.any?
        puts "#{team.name}: remove from MEMBERS['#{team.name}'] in tasks/org.rake: #{difference.join(', ')}"
      end
    end
  end

  desc 'Lists repositories that should be added or removed from teams'
  task :team_repos do
    # The repositories that should be accessible to these teams.
    datlab = [
      'kingfisher-process',
      'lib-cove-ocds',
      'ocdskit',
      'pelican',
    ]
    health = [
      'covid-19-procurement-explorer',
      'covid-19-procurement-explorer-admin',
      'covid-19-procurement-explorer-public',
    ]
    servers = [
      'deploy',
      'deploy-pillar-private',
      'deploy-salt-private',
      'dogsbody-maintenance',
    ]
    standard = [
      # Specifications
      'glossary',
      'infrastructure',
      'ocds-extensions',
      'standard',
      # Extension tools
      'extension_registry',
      'ocds-extensions-translations',
      # Internal tools
      'standard-development-handbook',
      # Documentation dependencies
      'european-union-support',
      # Templates
      'standard_extension_template',
      'standard_profile_template',
    ]

    repos = client.org_repos('open-contracting', per_page: 100)
    archived = repos.select(&:archived).map(&:name) - ['ocds-show', 'ocds-show-ppp']

    expected = {
      'General' => repos.map(&:name) - archived - servers - health,
      'Datlab' => datlab,
      'Health' => health,
      'Servers' => servers,
      'Standard' => standard,
    }

    client.org_teams('open-contracting').each do |team|
      team_repos = client.team_repos(team.id, per_page: 100).map(&:name)

      difference = team_repos - expected.fetch(team.name)
      if difference.any?
        puts "#{team.html_url}: remove from team: #{difference.join(', ')}"
      end
      difference = expected.fetch(team.name) - team_repos
      if difference.any?
        puts "#{team.html_url}: add to team: #{difference.join(', ')}"
      end
    end
  end

  desc 'Lists incorrect team repository permissions'
  task :team_perms do
    triage = [
      'ocds-extensions',
      'pelican',
    ]

    client.org_teams('open-contracting').each do |team|
      client.team_repos(team.id, per_page: 100).each do |team_repo|
        permissions = team_repo.permissions

        if triage.include?(team_repo.name)
          # Datlab has maintain privileges to its triage repositories. Others have triage privileges.
          expected = !permissions.pull && !permissions.push && !permissions.admin
          if team.name == 'Datlab'
            expected &&= !permissions.triage && permissions.maintain
          else
            expected &&= permissions.triage && !permissions.maintain
          end

          if !expected
            puts "#{team.html_url}/repositories: set #{team_repo.name} to #{team.name == 'Datlab' ? 'Maintain' : 'Triage'}"
          end
        else
          # Health has admin privileges to its non-triage repositories. Others have write privileges.
          expected = permissions.pull && permissions.push && !permissions.triage && !permissions.maintain
          if team.name == 'Health'
            expected &&= permissions.admin
          else
            expected &&= !permissions.admin
          end

          if !expected
            puts "#{team.html_url}/repositories: set #{team_repo.name} to #{team.name == 'Health' ? 'Admin' : 'Write'}"
          end
        end
      end
    end
  end
end
