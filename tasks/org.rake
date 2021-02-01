namespace :org do
  # Last updated 2020-04-09
  KNOWN_MEMBERS = [
    # Open Contracting Partnership
    # https://www.open-contracting.org/about/team/
    'jpmckinney', # James McKinney
    'lindseyam', # Lindsey Marchessault
    'yolile', # Yohanna Lisnichuk

    # Centro de Desarrollo Sostenible
    'aguilerapy', # Andrés Aguilera
    'nativaldezt', # Natalia Valdez

    # Datlab
    'jakubkrafka',
    'hrubyjan',

    # Dogsbody Technology Limited
    'dogsbody', # Dan Benton
    'dogsbody-ashley', # Ashley Holland
    'dogsbody-josh', # Josh Archer
    'jimacarter', # Jim Carter
    'robhooper', # Rob Hooper

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

    # Health

    # Transparency International
    'sean-darby',

    # Young Innovations
    'abhishekska',
    'anjesh',
    'anjila',
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

    # Standard
    'colinmaudry',
    'jachymhercher',
  ]

  ADMINS = Set.new([
    'bjwebb',
    'jpmckinney',
    'robredpath',
  ])

  desc 'Lists members that should be added or removed from the organization'
  task :members do
    organizations.each do |organization|
      people = client.org_members(organization, per_page: 100) + client.org_invitations(organization)

      names = people.map{ |member| member.login.downcase }

      difference = names - KNOWN_MEMBERS
      if difference.any?
        puts "#{organization}: add to tasks/org.rake: #{difference.join(', ')}"
      end

      if organization != 'open-contracting-extensions'
        difference = KNOWN_MEMBERS - names
        if difference.any?
          puts "#{organization}: remove from tasks/org.rake: #{difference.join(', ')}"
        end
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

  desc 'Lists repositories that should be added or removed from each team'
  task :team_repos do
    # The repositories that should be accessible to these teams.
    datlab = [
      'kingfisher-process',
      'lib-cove-ocds',
      'ocdskit',
      'pelican',
    ]
    servers = [
      'deploy',
      'deploy-pillar-private',
      'deploy-salt-private',
      'dogsbody-maintenance',
    ]
    health = [
      'covid-19-procurement-explorer',
      'covid-19-procurement-explorer-admin',
      'covid-19-procurement-explorer-public',
    ]

    # The repositories that should be triage only (e.g. no code).
    triage = [
      'ocds-extensions',
      'pelican',
    ]

    repos = client.org_repos('open-contracting', per_page: 100)
    repo_names = repos.map(&:name)

    archived = repos.select(&:archived).map(&:name) - ['ocds-show', 'ocds-show-ppp']

    {
      'General' => repo_names - archived - servers - health,
      'Servers' => servers,
      'Datlab' => datlab,
      'Health' => health,
    }.each do |team_name, expected|
      team = client.team_by_name('open-contracting', team_name)

      team_repos = client.team_repos(team.id, per_page: 100)
      team_repo_names = team_repos.map(&:name)

      team_repos.each do |team_repo|
        permissions = team_repo.permissions

        if triage.include?(team_repo.name)
          if !permissions.triage && team_name != 'Datlab'
            puts "#{team.html_url}: set #{team_repo.name} to Triage"
          elsif !permissions.maintain && team_name == 'Datlab'
            puts "#{team.html_url}: set #{team_repo.name} to Maintain"
          end
          if permissions.pull || permissions.push || permissions.admin
            puts "#{team.html_url}: #{team_repo.name} #{permissions}"
          end
        else
          if !permissions.push
            if team_name != 'Health'
              puts "#{team.html_url}: set #{team_repo.name} to Write"
            else
              puts "#{team.html_url}: set #{team_repo.name} to Admin"
            end
          end
          if permissions.admin && team_name != 'Health'
            puts "#{team.html_url}: set #{team_repo.name} to Write"
          elsif !permissions.admin && team_name == 'Health'
            puts "#{team.html_url}: set #{team_repo.name} to Admin"
          end
          if !permissions.pull || permissions.triage || permissions.maintain
            puts "#{team.html_url}: #{team_repo.name} #{permissions}"
          end
        end
      end

      difference = team_repo_names - expected
      if difference.any?
        puts "#{team.html_url}: remove from team: #{difference.join(', ')}"
      end
      difference = expected - team_repo_names
      if difference.any?
        puts "#{team.html_url}: add to team: #{difference.join(', ')}"
      end
    end
  end
end
