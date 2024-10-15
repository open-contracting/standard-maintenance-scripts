namespace :org do
  # Last updated 2022-12-13
  #
  # https://www.open-contracting.org/about/team/
  # http://opendataservices.coop
  MEMBERS = {
    'General' => [
      # Open Contracting Partnership
      'camilamila', # Camila Salazar
      'fppenna', # Félix Penna
      'ndrhzn', # Andrii Hazin
      'allakulov', # Umrbek Allakulov
    ],
    'OC4IDS' => [
      # Open Data Services Co-operative Limited
      'bjwebb', # Ben Webb
      'duncandewhurst', # Duncan Dewhurst
      'odscrachel', # Rachel Vint
      'neelima-j', # Neelima Janardhanan
      'odscjen', # Jen Harris
    ],
    'RBC Group' => [
      'a-radik',
      'andrzejbeletsky', # Andrzej Beletsky
      'karandinserhii', # Sergey Karandin
      'ndrhzn', # Andrii Hazin
      'ocds-bi-tools',
      'vgeryarbc', # Vadim Gerya
    ],
    'Robots' => [
      'ocp-deploy',
    ],
    'Standard' => [
      'colinmaudry', # Colin Maudry
      'jachymhercher', # Jachym Hercher
      # Open Data Services Co-operative Limited
      'duncandewhurst', # Duncan Dewhurst
      'odscjen', # Jen Harris
    ],
    'Servers' => [
      # Dogsbody Technology Limited
      'dogsbody', # Dan Benton
      'dogsbody-ashley', # Ashley Holland
      'dogsbody-josh', # Josh Archer
    ],
    'Transfers' => [
    ],
    'uStudio Design' => [
      'paulboroday', # Paul Boroday
    ],
  }

  ISSUES_ONLY = [
    'sabahfromlondon', # Sabah Zdanowska
    # Open Contracting Partnership
    'lindseyam', # Lindsey Marchessault
    'vtarnay1', # Volodymyr Tarnay
  ]

  ADMINS = [
    # Open Contracting Partnership
    'jpmckinney',
    'yolile',
  ]

  desc 'Lists members that should be added or removed from the organization'
  task :members do
    expected = MEMBERS.values.flatten

    organizations.each do |organization|
      people = client.org_members(organization, per_page: 100) + client.org_invitations(organization)
      names = people.map{ |member| member.login.downcase }

      difference = names - expected - ADMINS - ISSUES_ONLY
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
    dream_bi = [
      'bi.dream.gov.ua',
      'bi.dream.gov.ua-mdcp',
    ]
    # The repositories that should be accessible to these teams.
    rbcgroup = [
      'bi.open-contracting.org',
    ]
    oc4ids = [
      'cove-oc4ids',
      'infrastructure',
      'lib-cove-oc4ids',
      'notebooks-oc4ids',
      'oc4idskit',
    ]
    robots = [
      'deploy-salt-private',
      # lint.yml workflows using the stefanzweifel/git-auto-commit-action action with a personal access token (PAT).
      'cove-oc4ids',
      'cove-ocds',
      'credere-backend',
      'data-registry',
      'kingfisher-process',
      'kingfisher-summarize',
      'pelican-backend',
      'pelican-frontend',
    ]
    servers = [
      'deploy',
      'deploy-pillar-private',
      'deploy-salt-private',
    ]
    standard = [
      # Specifications
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
    ustudio_design = [
      'dream',
      'dream-api-docs',
    ]

    repos = client.org_repos('open-contracting', per_page: 100)
    archived = repos.select(&:archived).map(&:name)

    expected = {
      'General' => repos.map(&:name) - archived - servers - dream_bi - ustudio_design - ['backup-codes'],
      'OC4IDS' => oc4ids,
      'RBC Group' => rbcgroup + dream_bi,
      'Robots' => robots,
      'Servers' => servers,
      'Standard' => standard,
      'Transfers' => [],
      'uStudio Design' => ustudio_design,
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
    def human(permissions)
      perms = permissions.to_h.select{|_,v| v}.keys
      if perms.include?(:admin)
        'Admin'
      elsif perms.include?(:maintain)
        'Maintain'
      elsif perms.include?(:push)
        'Write'
      elsif perms.include?(:triage)
        'Triage'
      else
        'Read'
      end
    end

    issues_only_triage = [
      'ocds-extensions',
    ]

    # Issue-only repositories require Maintain permissions to add issues to projects.
    issues_only_maintain = [
    ]

    # Repositories under active development can have Maintain permissions.
    active_development = [
      'bi.dream.gov.ua',
      'bi.dream.gov.ua-mdcp',
      'dream',
      'dream-api-docs',
    ]

    client.org_teams('open-contracting').each do |team|
      client.team_repos(team.id, per_page: 100).each do |team_repo|
        permissions = team_repo.permissions

        if issues_only_maintain.include?(team_repo.name)
          expected = !permissions.pull && !permissions.push && !permissions.admin && !permissions.triage && permissions.maintain

          if !expected
            puts "#{team.html_url}/repositories: set #{team_repo.name} to 'Maintain' (was #{human(permissions)})"
          end
        elsif issues_only_triage.include?(team_repo.name)
          expected = permissions.pull && !permissions.push && !permissions.admin && permissions.triage && !permissions.maintain

          if !expected
            puts "#{team.html_url}/repositories: set #{team_repo.name} to 'Triage' (was #{human(permissions)})"
          end
        elsif team.name == 'Robots'
          expected = permissions.pull
          if team_repo.name != 'deploy-salt-private'
            expected &= permissions.push && permissions.triage && permissions.maintain && permissions.admin
          end

          if !expected
            puts "#{team.html_url}/repositories: set #{team_repo.name} to 'Admin' (was #{human(permissions)})"
          end
        else
          expected = permissions.pull && permissions.push && permissions.triage && !permissions.admin
          if active_development.include?(team_repo.name)
            expected &&= permissions.maintain
            human_permission = 'Admin'
          else
            expected &&= !permissions.maintain
            human_permission = 'Write'
          end

          if !expected
            puts "#{team.html_url}/repositories: set #{team_repo.name} to '#{human_permission}' (was #{human(permissions)})"
          end
        end
      end
    end
  end
end
