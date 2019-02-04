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
  desc "Disables empty wikis, updates extensions' descriptions and homepages, and lists repositories with invalid names, unexpected configurations, etc."
  task :lint_repos do
    repos.each do |repo|
      if extension?(repo.name, profiles: false, templates: false)
        metadata = JSON.load(read_github_file(repo.full_name, 'extension.json'))
        options = {}

        description = metadata['description'].fetch('en')
        if description != repo.description
          options[:description] = description
        end

        homepage = metadata['documentationUrl'].fetch('en')
        if homepage == repo.html_url || homepage['https://github.com/open-contracting']
          homepage = nil # don't link to itself
        end
        if homepage != repo.homepage
          options[:homepage] = homepage
        end

        if options.any?
          client.edit_repository(repo.full_name, options.dup)
          puts "#{repo.html_url} #{"updated #{options.keys.join(' and ')}".bold}"
        end
      end

      if repo.has_wiki
        response = Faraday.get("#{repo.html_url}/wiki")
        if response.status == 302 && response.headers['location'] == repo.html_url
          client.edit_repository(repo.full_name, has_wiki: false)
          puts "#{repo.html_url}/settings #{'disabled wiki'.bold}"
        end
      end

      if extension?(repo.name, profiles: false, templates: false)
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
    headers = {accept: 'application/vnd.github.luke-cage-preview+json'} # branch_protection

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

      if repo.rels[:hooks].get.data.any?{ |datum| datum.name == 'travis' || datum.config.url == 'https://notify.travis-ci.org' }
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
      if ['standard', 'public-private-partnerships'].include?(repo.name)
        branches_to_protect << branches.find{ |branch| branch.name == 'latest' }
        branches.each do |branch|
          if branch.name[/\A\d\.\d(?:-dev)?\z/]
            branches_to_protect << branch
          end
        end
      end

      options = headers.merge({
        enforce_admins: false,
        required_status_checks: {
          strict: false,
          contexts: contexts,
        },
        required_pull_request_reviews: nil,
      })

      if ENFORCE_ADMINS.include?(repo.name)
        options[:enforce_admins] = true
      end

      if REQUIRE_PULL_REQUEST_REVIEWS.include?(repo.name)
        options[:required_pull_request_reviews] = {
          required_approving_review_count: 1,
          dismiss_stale_reviews: true,
        }
      end

      branches_to_protect.each do |branch|
        branch = client.branch(repo.full_name, branch.name)

        if !branch.protected
          client.protect_branch(repo.full_name, branch.name, options)
          puts "#{repo.html_url}/settings/branches/#{branch.name} #{'protected'.bold}"
        else
          protection = client.branch_protection(repo.full_name, branch.name, headers)

          if (options[:enforce_admins] && !protection.enforce_admins.enabled ||
              !options[:enforce_admins] && protection.enforce_admins.enabled ||
              protection.required_status_checks && protection.required_status_checks.strict ||
              protection.required_status_checks && protection.required_status_checks.contexts != contexts && known_contexts.include?(protection.required_status_checks.contexts) ||
              options[:required_pull_request_reviews] && !protection.required_pull_request_reviews ||
              !options[:required_pull_request_reviews] && protection.required_pull_request_reviews)
            messages = []

            if options[:enforce_admins]
              if !protection.enforce_admins.enabled
                messages << "check 'Include administrators'"
              end
            else
              if protection.enforce_admins.enabled
                messages << "uncheck 'Include administrators'"
              end
            end
            if protection.required_status_checks && protection.required_status_checks.strict
              messages << "uncheck 'Require branches to be up to date before merging'"
            end
            if options[:required_pull_request_reviews]
              if !protection.required_pull_request_reviews || !protection.required_pull_request_reviews.dismiss_stale_reviews
                messages << "check 'Dismiss stale pull request approvals when new commits are pushed'"
              end
              if !protection.required_pull_request_reviews || protection.required_pull_request_reviews.required_approving_review_count != 1
                messages << "Set 'Required approving reviews' to 1"
              end
            else
              if protection.required_pull_request_reviews
                messages << "uncheck 'Require pull request reviews before merging'"
              end
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
            puts "#{repo.html_url}/settings/branches #{messages.join(' | ').bold}"
          elsif protection.required_status_checks.contexts != contexts
            puts "#{repo.html_url}/settings/branches expected #{contexts.join(', ')}, got #{protection.required_status_checks.contexts.join(', ').bold}"
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

      print '.'
    end
  end

  desc 'Sets topics of extensions'
  task :set_topics do
    repos.each do |repo|
      topics = []

      if extension?(repo.name, profiles: false, templates: false)
        topics << 'ocds-extension'
        if core_extensions.key?(repo.full_name)
          if core_extensions[repo.full_name]
            topics << 'ocds-core-extension'
          else
            topics << 'ocds-community-extension'
          end
        else
          puts "extension not in registry: #{repo.full_name}"
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

        hook = repo.rels[:hooks].get.data.find{ |datum| datum.name == 'travis' || datum.config.url == 'https://notify.travis-ci.org' }
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
