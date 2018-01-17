def disable_issues(repo, message)
  if repo.has_issues
    open_issues = repo.open_issues - repo.rels[:pulls].get.data.size
    if open_issues.zero?
      client.edit_repository(repo.full_name, has_issues: false)
      puts "#{repo.html_url}/settings #{'disabled issues'.bold}"
    else
      puts "#{repo.html_url}/issues #{"issues #{message}".bold}"
    end
  end
end

def disable_projects(repo, message)
  if repo.has_projects
    projects = client.projects(repo.full_name, accept: 'application/vnd.github.inertia-preview+json') # projects
    if projects.none?
      client.edit_repository(repo.full_name, has_projects: false)
      puts "#{repo.html_url}/settings #{'disabled projects'.bold}"
    else
      puts "#{repo.html_url}/issues #{"projects #{message}".bold}"
    end
  end
end

namespace :fix do
  desc 'Disables empty wikis and lists repositories with invalid names, unexpected configurations, etc.'
  task :lint_repos do
    repos.each do |repo|
      if repo.has_wiki
        response = Faraday.get("#{repo.html_url}/wiki")
        if response.status == 302 && response.headers['location'] == repo.html_url
          client.edit_repository(repo.full_name, has_wiki: false)
          puts "#{repo.html_url}/settings #{'disabled wiki'.bold}"
        end
      end

      if extension?(repo.name, true)
        if !repo.name[/\Aocds_\w+_extension\z/]
          puts "#{repo.name} is not a valid extension name"
        end

        disable_issues(repo, 'should be moved and disabled')
        disable_projects(repo, 'should be moved and disabled')
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

  desc 'Protects default branches'
  task :protect_branches do
    headers = {accept: 'application/vnd.github.loki-preview+json'} # branch_protection

    known_contexts = Set.new([
      # Unconfigured.
      [],
      # Configured with Travis.
      ['continuous-integration/travis-ci'],
    ])

    repos.each do |repo|
      contexts = []

      # The GitHub Pages status check is very slow.
      # if repo.has_pages
      #   contexts << 'github/pages'
      # end

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

      options = headers.merge({
        enforce_admins: true,
        required_status_checks: {
          strict: false,
          contexts: contexts,
        },
        required_pull_request_reviews: nil,
      })

      branches_to_protect.each do |branch|
        branch = client.branch(repo.full_name, branch.name)

        if !branch.protected
          client.protect_branch(repo.full_name, branch.name, options)
          puts "#{repo.html_url}/settings/branches/#{branch.name} #{'protected'.bold}"
        else
          protection = client.branch_protection(repo.full_name, branch.name, headers)

          if (!protection.enforce_admins.enabled ||
              protection.required_status_checks.strict ||
              protection.required_status_checks.contexts != contexts && known_contexts.include?(protection.required_status_checks.contexts) ||
              protection.required_pull_request_reviews)
            messages = []

            if !protection.enforce_admins.enabled
              messages << "check 'Include administrators'"
            end
            if protection.required_status_checks.strict
              messages << "uncheck 'Require branches to be up to date before merging'"
            end
            if protection.required_pull_request_reviews
              messages << "uncheck 'Require pull request reviews before merging'"
            end

            added = contexts - branch.protection.required_status_checks.contexts
            if added.any?
              messages << "added: #{added.join(', ')}"
            end

            removed = branch.protection.required_status_checks.contexts - contexts
            if removed.any?
              messages << "removed: #{removed.join(', ')}"
            end

            client.protect_branch(repo.full_name, branch.name, options)
            puts "#{repo.html_url}/settings/branches/#{branch.name} #{messages.join(' | ').bold}"
          elsif protection.required_status_checks.contexts != contexts
            puts "#{repo.html_url}/settings/branches/#{branch.name} expected #{contexts.join(', ')}, got #{protection.required_status_checks.contexts.join(', ').bold}"
          end
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

  desc 'Sets topics of extensions'
  task :set_topics do
    core_extensions = {}
    JSON.load(open('http://standard.open-contracting.org/extension_registry/master/extensions.json').read)['extensions'].each do |extension|
      match = extension['url'].match(%r{\Ahttps://raw\.githubusercontent\.com/[^/]+/([^/]+)/master/\z})
      if match
        core_extensions[match[1]] = extension.fetch('core')
      else
        raise "couldn't determine extension name: #{extension['url']}"
      end
    end

    repos.each do |repo|
      topics = []

      if extension?(repo.name, true)
        topics << 'ocds-extension'
        if core_extensions.key?(repo.name)
          if core_extensions[repo.name]
            topics << 'ocds-core-extension'
          else
            topics << 'ocds-community-extension'
          end
        else
          puts "couldn't find extension in registry: #{repo.name}"
        end
      end

      if topics.any?
        client.replace_all_topics(repo.full_name, topics, accept: 'application/vnd.github.mercy-preview+json')
      end
    end
  end

  desc 'Prepares repositories for archival'
  task :archive_repos do
    if ENV['REPOS']
      repos.each do |repo|
        disable_issues(repo, 'should be reviewed')
        disable_projects(repo, 'should be reviewed')

        hook = repo.rels[:hooks].get.data.find{ |datum| datum.name == 'travis' }
        if hook
          client.remove_hook(repo.full_name, hook.id)
        end

        if !repo.archived
          puts "#{repo.html_url}/settings #{'should be archived'.bold}"
        end
      end
    else
      abort "You must set the REPOS environment variable to archive repositories."
    end
  end
end
