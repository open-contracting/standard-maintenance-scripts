namespace :org do
  # Last updated 2020-04-09
  KNOWN_MEMBERS = [
    # Open Contracting Partnership
    # https://www.open-contracting.org/about/team/
    'jpmckinney', # James McKinney
    'lindseyam', # Lindsey Marchessault

    # Centro de Desarrollo Sostenible
    'aguilerapy', # Andrés Aguilera
    'juanpane', # Juan Pane
    'nativaldezt', # Natalia Valdez
    'yolile', # Yohanna Lisnichuk

    # Datlab
    'jakubkrafka',
    'hrubyjan',

    # Dogsbody Technology Limited
    'dogsbody', # Dan Benton
    'dogsbody-ashley', # Ashley Holland
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
    'odscjames', # James Baster
    'rhiaro', # Amy Guy
    'robredpath', # Rob Redpath
    'tim0th1', # Tim Williams
    # 'bibianac', # Bibiana Cristofol
    # 'idlemoor', # David Spencer
    # 'rory09', # Rory Scott
    # 'scatteredink', # Jack Lord

    # Transparency International
    'sean-darby',

    # Young Innovations
    'prashantsh',
  ]

  ADMINS = Set.new([
    'bjwebb',
    'jpmckinney',
    'robredpath',
  ])

  desc 'Lists members not employed by the Open Contracting Partnership or its helpdesk teams'
  task :members do
    organizations.each do |organization|
      people = client.org_members(organization) + client.org_invitations(organization)

      names = people.map{ |member| member.login.downcase }

      difference = names - KNOWN_MEMBERS - ['colinmaudry']
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
        if collaborator.permissions.admin && !ADMINS.include?(login)
          if owner == 'open-contracting-extensions' && login == 'colinmaudry'
            client.add_collaborator(repo.full_name, collaborator.login, permission: 'maintain')
            puts "#{repo.html_url}/settings/access changed #{collaborator.login.bold} from 'admin' to 'maintain'"
          else
            client.remove_collaborator(repo.full_name, collaborator.login)
            puts "#{repo.html_url}/settings/access removed #{collaborator.login.bold}"
          end
        else
          puts "#{repo.html_url}/settings/access #{collaborator.login}"
        end
      end
    end
  end

  desc 'Lists repositories that should be added or removed from each team'
  task :team_repos do
    repos = client.org_repos('open-contracting', per_page: 100)
    archived = repos.select(&:archived).map(&:name) - ['ocds-show', 'ocds-show-ppp']
    deploy = ['deploy', 'deploy-pillar-private', 'deploy-salt-private', 'dogsbody-maintenance']
    datlab = ['pelican', 'kingfisher-process']
    young_innovations = ['covid-19-procurement-explorer']
    repo_names = repos.map(&:name)

    {
      'General' => repo_names - archived - deploy - young_innovations,
      'Servers' => deploy,
      'Datlab' => datlab,
      'Health' => young_innovations,
    }.each do |team_name, expected|
      team = client.team_by_name('open-contracting', team_name)
      team_repos = client.team_repos(team.id, per_page: 100).map(&:name)

      difference = team_repos - expected
      if difference.any?
        puts "#{team.html_url}: remove from team: #{difference.join(', ')}"
      end
      difference = expected - team_repos
      if difference.any?
        puts "#{team.html_url}: add to team: #{difference.join(', ')}"
      end
    end
  end
end
