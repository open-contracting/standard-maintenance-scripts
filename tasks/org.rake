namespace :org do
  desc 'Lists organization members not employed by the Open Contracting Partnership or its helpdesk teams'
  task :members do
    # Last updated 2018-01-15
    known_members = [
      # Open Contracting Partnership
      # https://www.open-contracting.org/about/team/
      'jpmckinney', # James McKinney
      'lindseyam', # Lindsey Marchessault

      # Open Data Services Co-operative Limited
      # http://opendataservices.coop
      'bibianac', # Bibiana Cristofol
      'bjwebb', # Ben Webb
      'duncandewhurst', # Duncan Dewhurst
      'idlemoor', # David Spencer
      'kindly', # David Raznick
      'michaelwood', # Michael Wood
      'mrshll1001', # Matt Marshall
      'odscjames', # James Baster
      'pindec', # Charlie Pinder
      'rhiaro', # Amy Guy
      'robredpath', # Rob Redpath
      'tim0th1', # Tim Williams
      # 'rory09', # Rory Scott
      # 'scatteredink', # Jack Lord

      # Centro de Desarrollo Sostenible
      'aguilerapy', # Andrés Aguilera
      'juanpane', # Juan Pane
      'romifz', # Romina Fernández Valdez
      'yolile', # Yohanna Lisnichuk

      # Consultants
      'colinmaudry', # Colin Maudry
    ]

    organizations.each do |organization|
      people = client.org_members(organization) + client.org_invitations(organization)

      names = people.map{ |member| member.login.downcase }

      difference = names - known_members
      if difference.any?
        puts "#{organization}: add to tasks/org.rake: #{difference.join(', ')}"
      end

      if organization != 'open-contracting-extensions'
        difference = known_members - names
        if difference.any?
          puts "#{organization}: remove from tasks/org.rake: #{difference.join(', ')}"
        end
      end
    end
  end
end
