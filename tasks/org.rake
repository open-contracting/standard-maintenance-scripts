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
      'kindly', # David Raznick
      'odscjames', # James Baster
      'rhiaro', # Amy Guy
      'robredpath', # Rob Redpath
      'rory09', # Rory Scott
      'scatteredink', # Jack Lord
      'tim0th1', # Tim Williams
      'timgdavies', # Tim Davies

      # Iniciativa Latinoamericana por los Datos Abiertos
      # https://idatosabiertos.org/acerca-de-nosotros/
      'juanpane', # Juan Pane
      'scrollif', # Fabrizio Scrollini
      'tian2992', # Sebastian Oliva
      'yolile', # Yohanna Lisnichuk
    ]

    organizations.each do |organization|
      people = client.org_members(organization) + client.org_invitations(organization)

      names = people.map{ |member| member.login.downcase }

      difference = names - known_members
      if difference.any?
        puts "#{organization}: add to tasks/org.rake: #{difference.join(', ')}"
      end

      difference = known_members - names
      if difference.any?
        puts "#{organization}: remove from tasks/org.rake: #{difference.join(', ')}"
      end
    end
  end
end
