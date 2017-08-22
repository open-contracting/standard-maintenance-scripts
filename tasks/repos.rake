namespace :repos do
  desc 'Checks Travis configurations'
  task :check_travis do
    def read(repo, path)
      Base64.decode64(client.contents(repo, path: path).content)
    end

    expected = read('open-contracting/standard-maintenance-scripts', 'fixtures/.travis.yml')

    repos.each do |repo|
      if repo.rels[:hooks].get.data.any?{ |datum| datum.name == 'travis' }
        begin
          actual = read(repo.full_name, '.travis.yml')
          if actual != expected
            if HashDiff.diff(YAML.load(actual), YAML.load(expected)).reject{ |diff| diff[0] == '-' }.any?
              puts "#{repo.html_url}/blob/#{repo.default_branch}/.travis.yml lacks configuration"
            end
          end
        rescue Octokit::NotFound
          puts "#{repo.html_url} lacks .travis.yml"
        end
      else
        puts "#{repo.html_url} lacks Travis"
      end
    end
  end

  desc 'Lists repositories with many non-PR branches'
  task :many_branches do
    exclusions = Set.new((ENV['EXCLUDE'] || '').split(','))

    repos.each do |repo|
      pulls = repo.rels[:pulls].get.data.map{ |pull| pull.head.ref }

      branches = repo.rels[:branches].get.data.reject do |branch|
        branch.name == repo.default_branch || exclusions.include?(branch.name) || pulls.include?(branch.name)
      end

      if branches.any?
        puts "#{repo.html_url}/branches"
        puts "  #{branches.size}: #{branches.map(&:name).join(' ')}"
      end
    end
  end

  desc 'Protects default branches'
  task :protect_branches do
    headers = {accept: 'application/vnd.github.loki-preview+json'}

    known_contexts = Set.new([
      # Unconfigured.
      [],
      # Configured with Travis.
      ['continuous-integration/travis-ci'],
    ])

    repos.each do |repo|
      contexts = []
      if repo.rels[:hooks].get.data.any?{ |datum| datum.name == 'travis' }
        begin
          # Only enable Travis if Travis is configured.
          client.contents(repo.full_name, path: '.travis.yml')
          contexts << 'continuous-integration/travis-ci'
        rescue Octokit::NotFound
          # Do nothing.
        end
      end

      branches = repo.rels[:branches].get(headers: headers).data

      branches_to_protect = [branches.find{ |branch| branch.name == repo.default_branch }]
      if repo.name == 'standard'
        branches_to_protect << branches.find{ |branch| branch.name == 'latest' }
        branches.each do |branch|
          if branch.name[/\A\d\.\d(?:-dev)?\z/]
            branches_to_protect << branch
          end
        end
      end

      options = headers.merge(enforce_admins: true, required_status_checks: {strict: true, contexts: contexts})
      branches_to_protect.each do |branch|
        if !branch.protected
          client.protect_branch(repo.full_name, branch.name, options)
          puts "#{repo.html_url}/settings/branches/#{branch.name} protected"
        elsif branch.protection.enabled && branch.protection.required_status_checks.enforcement_level == 'everyone' && known_contexts.include?(branch.protection.required_status_checks.contexts) && branch.protection.required_status_checks.contexts != contexts
          client.protect_branch(repo.full_name, branch.name, options)

          messages = []

          added = contexts - branch.protection.required_status_checks.contexts
          if added.any?
            messages << "added: #{added.join(', ')}"
          end

          removed = branch.protection.required_status_checks.contexts - contexts
          if removed.any?
            messages << "removed: #{removed.join(', ')}"
          end

          puts "#{repo.html_url}/settings/branches/#{branch.name} #{messages.join(' | ').bold}"
        elsif !branch.protection.enabled || branch.protection.required_status_checks.enforcement_level != 'everyone' || branch.protection.required_status_checks.contexts != contexts
          puts "#{repo.html_url}/settings/branches/#{branch.name} unexpectedly configured"
        end
      end


      expected_protected_branches = branches_to_protect.map(&:name)
      unexpected_protected_branches = branches.select{ |branch| branch.protected && !expected_protected_branches.include?(branch.name) }
      if unexpected_protected_branches.any?
        puts "#{repo.html_url}/settings/branches unexpectedly protects:" 
        unexpected_protected_branches.each do |branch|
          puts "- #{branch.name}"
        end
      end
    end
  end

  desc 'Lists missing or unexpected licenses'
  task :licenses do
    repos.partition{ |repo| extension?(repo.name) }.each do |set|
      puts
      set.each do |repo|
        if repo.license.nil? || repo.license.key != 'apache-2.0'
          puts "#{repo.html_url} #{repo.license && repo.license.key.bold}"
        end
      end
    end
  end

  desc 'Lists repository descriptions'
  task :descriptions do
    repos.partition{ |repo| extension?(repo.name) }.each do |set|
      puts
      set.each do |repo|
        puts "#{repo.html_url}\n- #{repo.description}"
      end
    end
  end

  desc 'Lists non-default issue labels'
  task :labels do
    default_labels = ['bug', 'duplicate', 'enhancement', 'help wanted', 'invalid', 'question', 'wontfix']

    repos.each do |repo|
      data = repo.rels[:labels].get.data
      remainder = data.map(&:name).reject{ |name| name[/\A\d - /] } - default_labels # exclude HuBoard labels
      if remainder.any?
        puts "#{repo.html_url}/labels"
        data.each do |datum|
          puts "- #{datum.name}"
        end
      end
    end
  end

  desc 'Lists releases'
  task :releases do
    repos.each do |repo|
      data = repo.rels[:releases].get.data
      if data.any?
        puts "#{repo.html_url}/releases"
        data.each do |datum|
          puts "- #{datum.tag_name}: #{datum.name}"
        end
      end
    end
  end

  desc 'Lists unreleased tags'
  task :tags do
    repos.each do |repo|
      tags = repo.rels[:tags].get.data.map(&:name) - repo.rels[:releases].get.data.map(&:tag_name)
      if repo.fork
        tags -= client.repo(repo.full_name).parent.rels[:tags].get.data.map(&:name)
      end
      if tags.any?
        puts "#{repo.html_url}/tags"
        tags.each do |tag|
          puts "- #{tag}"
        end
      end
    end
  end

  desc 'Lists non-Travis webhooks'
  task :webhooks do
    repos.each do |repo|
      data = repo.rels[:hooks].get.data.select{ |datum| datum.name != 'travis' }
      if data.any?
        puts "#{repo.html_url}/settings/hooks"
        data.each do |datum|
          puts "- #{datum.name} #{datum.config.url}"
        end
      end
    end
  end

  desc 'Disables empty wikis and lists repositories with invalid names, unexpected configurations, etc.'
  task :lint do
    repos.each do |repo|
      if repo.has_wiki
        response = Faraday.get("#{repo.html_url}/wiki")
        if response.status == 302 && response.headers['location'] == repo.html_url
          client.edit_repository(repo.full_name, has_wiki: false)
          puts "#{repo.html_url}/settings disabled wiki"
        end
      end

      if extension?(repo.name) && !repo.name[/\Aocds_\w+_extension\z/]
        puts "#{repo.name} is not a valid extension name"
      end

      if repo.private
        puts "#{repo.html_url} is private"
      end

      {
        # The only deployments should be for GitHub Pages.
        deployments: {
          path: ' (deployments)',
          filter: -> (datum) { datum.environment != 'github-pages' },
        },
        # Repositories shouldn't have deploy keys.
        keys: {
          path: '/settings/keys',
        },
      }.each do |rel, config|
        filter = config[:filter] || -> (datum) { true }
        formatter = config[:formatter] || -> (datum) { "- #{datum.inspect}" }

        data = repo.rels[rel].get.data.select(&filter)
        if data.any?
          puts "#{repo.html_url}#{config[:path]}"
          data.each do |datum|
            puts formatter.call(datum)
          end
        end
      end
    end
  end

  desc 'Lists repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled'
  task :status do
    format = '%-50s  %11s  %11s  %11s  %11s  %s  %s  %s  %s'

    repos.partition{ |repo| extension?(repo.name) }.each do |set|
      puts '%-50s  %s  %s  %s  %s  %s  %s  %s  %s' % ['', '#I', '#P', '#B', '#M', 'W', 'P', 'I', 'P']

      set.sort{ |a, b|
        if a.open_issues == b.open_issues
          a.name <=> b.name
        else
          a.open_issues <=> b.open_issues
        end
      }.each do |repo|
        pull_requests = repo.rels[:pulls].get.data.size

        puts format % [
          repo.name,
          i(repo.open_issues - pull_requests),
          i(pull_requests),
          i(repo.rels[:branches].get.data.size - 1),
          i(repo.rels[:milestones].get.data.size),
          s(repo.has_wiki),
          s(repo.has_pages),
          s(repo.has_issues),
          s(repo.has_projects),
        ]
      end
    end
  end
end
