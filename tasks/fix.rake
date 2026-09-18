namespace :fix do
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
      if open_projects_count(repo).zero?
        client.edit_repository(repo.full_name, has_projects: false)
        puts "#{repo.html_url}/settings #{'disabled projects'.bold}"
      else
        puts "#{repo.html_url}/projects #{"projects #{message}".bold}"
      end
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
