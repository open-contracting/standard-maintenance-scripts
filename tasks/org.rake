namespace :org do
  desc 'Lists organization members'
  task :members do
    # Last updated 2017-08-14
    known_members = [
      # Open Contracting Partnership
      # https://www.open-contracting.org/about/team/
      'jpmckinney', # James McKinney
      'lindseyam', # Lindsey Marchessault

      # Open Data Services Co-op
      # http://opendataservices.coop
      'bjwebb', # Ben Webb
      'caprenter', # David Carpenter
      'duncandewhurst', # Duncan Dewhurst
      'edugomez', # Eduardo Gomez
      'julijahansen', # Julija Hansen
      'kindly', # David Raznick
      'robredpath', # Rob Redpath
      'timgdavies', # Tim Davies

      # Iniciativa Latinoamericana por los Datos Abiertos
      # https://idatosabiertos.org/acerca-de-nosotros/
      'cdemidchuk', # Catalina Demidchuk
      'emanuelzh', # Emanuel Zámano
      'juanpane', # Juan Pane
      'scrollif', # Fabrizio Scrollini
      'tlacoyodefrijol', # Oscar Montiel
      'yolile', # Yohanna Lisnichuk
    ]

    people = client.org_members(organization) + client.org_invitations(organization, accept: 'application/vnd.github.korra-preview')

    puts people.map{ |member| member.login.downcase } - known_members
  end
end
