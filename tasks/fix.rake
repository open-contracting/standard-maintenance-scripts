namespace :fix do
  REQUIRE_PULL_REQUEST_REVIEWS = [
    'cove-oc4ids',
    'cove-ocds',
    'kingfisher-archive',
    'kingfisher-collect',
    'kingfisher-process',
    'kingfisher-vagrant',
    'kingfisher-summarize',
    'lib-cove-oc4ids',
    'lib-cove-ocds',
    'notebooks-oc4ids',
  ]
  ENFORCE_ADMINS = [
    'public-private-partnerships',
    'standard',
  ]

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

  def protect_branch(repo, branch, options, messages=[])
    client.protect_branch(repo.full_name, branch.name, options)
    puts "#{repo.html_url}/settings/branches #{branch.name}: #{messages.join(' | ').bold}"

    # Need to switch to GraphQL API, otherwise. "To use wildcard characters in branch names, use the GraphQL API."
    if extension?(repo.name, profiles: false, templates: false) && branch.name == "1.1"
      puts "#{repo.html_url}/settings/branches: #{'rename the branch name pattern from 1.1 to 1.?'.red}"
    end
  end

  desc "Enables delete branch on merge, disables empty wikis, updates extensions' descriptions and homepages, and lists repositories with invalid names, unexpected configurations, etc."
  task :lint_repos do
    repos.each do |repo|
      if repo.archived
        next
      end

      # allow_auto_merge and delete_branch_on_merge are not returned by org_repos.
      repo = client.repo(repo.full_name)
      options = {}

      # "Automatically delete head branches"
      if not repo.delete_branch_on_merge
        options[:delete_branch_on_merge] = true
      end

      # "Allow squash merging"
      if not repo.allow_squash_merge
        options[:allow_squash_merge] = true
      end

      # "Allow auto-merge"
      if profile?(repo.name) or specification?(repo.name) or repo.name == 'standard_profile_template'
        # Merging causes a deployment. Only merge PRs manually.
        if repo.allow_auto_merge
          options[:allow_auto_merge] = false
        end
      elsif has_github_file(repo.full_name, '.github/workflows/deploy.yml')
        # Merging causes a deployment. Only merge PRs manually.
        if repo.allow_auto_merge
          options[:allow_auto_merge] = false
        end
      elsif not repo.allow_auto_merge
        if has_github_file(repo.full_name, '.github/dependabot.yml')
          options[:allow_auto_merge] = true
        end
      end

      # Extensions
      if extension?(repo.name, profiles: false, templates: false)
        # Name
        if !repo.name[/\Aocds_\w+_extension\z/]
          puts "#{repo.name} is not a valid extension name"
        end

        # Issues and projects
        disable_issues(repo, 'should be moved and disabled')
        disable_projects(repo, 'should be moved and disabled')

        metadata = JSON.load(read_github_file(repo.full_name, 'extension.json'))
        if !metadata.nil?
          # Description
          description = metadata['description'].fetch('en')
          if description != repo.description
            options[:description] = description
          end

          # Homepage
          homepage = metadata['documentationUrl'].fetch('en')
          if homepage == repo.html_url || homepage['https://github.com/open-contracting']
            homepage = nil # don't link to itself
          end
          if homepage != repo.homepage
            options[:homepage] = homepage
          end
        else
          puts "#{repo.html_url} #{"no extension.json file!".bold}"
        end
      end

      # Wiki
      if repo.has_wiki
        response = Faraday.get("#{repo.html_url}/wiki")
        if response.status == 302 && response.headers['location'] == repo.html_url
          options[:has_wiki] = false
        end
      end

      if options.any?
        client.edit_repository(repo.full_name, options.dup)
        puts "#{repo.html_url}"
        options.each do |key, value|
          if value == true
            puts "- enabled #{key}".bold
          elsif value == false
            puts "- disabled #{key}".bold
          else
            puts "- updated #{key}".bold
          end
        end
      end

      # Private
      if repo.private
        puts "#{repo.html_url} is #{"private".yellow}"
      end

      # Deployments and keys
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

    repos.each do |repo|
      contexts = []

      ci = read_github_file(repo.full_name, '.github/workflows/ci.yml')
      lint = read_github_file(repo.full_name, '.github/workflows/lint.yml')

      if !ci.empty? || !lint.empty?
        if repo.owner.login == 'open-contracting-extensions'
          contexts << 'lint / build'
        else
          contexts << 'build'
        end
      end

      branches = repo.rels[:branches].get(headers: headers).data

      branches_to_protect = [branches.find{ |branch| branch.name == repo.default_branch }]
      if ['standard', 'public-private-partnerships', 'infrastructure'].include?(repo.name)
        branches.each do |branch|
          if branch.name[/\A\d\.\d(?:-dev)?\z/]
            branches_to_protect << branch
          end
        end
      end
      branches_to_protect.uniq!

      if not branches_to_protect
        raise "no branches to protect"
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

        enforce_admins = options[:enforce_admins]
        if repo.name == 'public-private-partnerships' && branch.name.end_with?('-dev')
          enforce_admins = false
        end

        if !branch.protected
          protect_branch(repo, branch, options, ['protected'])
        else
          protection = client.branch_protection(repo.full_name, branch.name, headers)

          if (enforce_admins && !protection.enforce_admins.enabled ||
              !enforce_admins && protection.enforce_admins.enabled ||
              protection.required_status_checks && protection.required_status_checks.strict ||
              protection.required_status_checks && protection.required_status_checks.contexts != contexts ||
              protection.required_status_checks.nil? ||
              options[:required_pull_request_reviews] && !protection.required_pull_request_reviews ||
              !options[:required_pull_request_reviews] && protection.required_pull_request_reviews)
            messages = []

            if enforce_admins
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
                messages << "set 'Required approving reviews' to 1"
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

            protect_branch(repo, branch, options, messages)
          elsif protection.required_status_checks.contexts != contexts
            puts "#{repo.html_url}/settings/branches expected #{contexts.join(', ')}, got #{protection.required_status_checks.contexts.join(', ').bold}"
          end
        end
      end

      expected_protected_branches = branches_to_protect.map(&:name)
      unexpected_protected_branches = branches.select do |branch|
        branch.protected && !expected_protected_branches.include?(branch.name) &&
        # "1.2" branches are allowed on extensions whose default branch is "1.1".
        (!extension?(repo.name, profiles: false, templates: false) || repo.default_branch != "1.1" || branch.name != "1.2")
      end
      if unexpected_protected_branches.any?
        puts "#{repo.html_url}/settings/branches unexpectedly protects #{unexpected_protected_branches.map(&:name).join(' and ').bold}"
      end

      print '.'
    end
  end

  desc 'Prepares repositories for archival'
  task :archive_repos do
    if ENV['REPOS']
      repos.each do |repo|
        disable_issues(repo, 'should be reviewed')
        disable_projects(repo, 'should be reviewed')

        if !repo.archived
          puts "#{repo.html_url}/settings #{'should be archived'.bold}"
        end
      end
    else
      abort "You must set the REPOS environment variable to archive repositories."
    end
  end
end
