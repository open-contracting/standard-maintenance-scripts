namespace :org do
  # Last updated 2020-04-09
  KNOWN_MEMBERS = [
    # Open Contracting Partnership
    # https://www.open-contracting.org/about/team/
    'jpmckinney', # James McKinney
    'lindseyam', # Lindsey Marchessault

    # Open Data Services Co-operative Limited
    # http://opendataservices.coop
    'duncandewhurst', # Duncan Dewhurst
    'mrshll1001', # Matt Marshall
    'pindec', # Charlie Pinder
    # Developers
    'bjwebb', # Ben Webb
    'idlemoor', # David Spencer
    'kindly', # David Raznick
    'odscjames', # James Baster
    'rhiaro', # Amy Guy
    'robredpath', # Rob Redpath
    'tim0th1', # Tim Williams
    # 'bibianac', # Bibiana Cristofol
    # 'michaelwood', # Michael Wood
    # 'rory09', # Rory Scott
    # 'scatteredink', # Jack Lord

    # Centro de Desarrollo Sostenible
    'aguilerapy', # Andrés Aguilera
    'juanpane', # Juan Pane
    'romifz', # Romina Fernández Valdez
    'yolile', # Yohanna Lisnichuk
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
      repo.rels[:collaborators].get.data.each do |collaborator|
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
        end
      end
    end
  end
end
