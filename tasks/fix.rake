namespace :fix do
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

      if extension?(repo.name)
        if !repo.name[/\Aocds_\w+_extension\z/]
          puts "#{repo.name} is not a valid extension name"
        end

        open_issues = repo.open_issues - repo.rels[:pulls].get.data.size
        if repo.has_issues && open_issues.zero?
          client.edit_repository(repo.full_name, has_issues: false)
          puts "#{repo.html_url}/settings #{'disabled issues'.bold}"
        end

        if repo.has_projects && client.projects(repo.full_name, accept: 'application/vnd.github.inertia-preview+json').none?
          client.edit_repository(repo.full_name, has_projects: false)
          puts "#{repo.html_url}/settings #{'disabled projects'.bold}"
        end
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

  desc 'Update extension readmes with template content'
  task :update_readmes do
    basedir = variables('BASEDIR')[0]

    template = <<-END

## Issues

Report issues for this extension in the [ocds-extensions repository](https://github.com/open-contracting/ocds-extensions/issues), putting the extension's name in the issue's title.
    END

    updated = []

    Dir[File.join(basedir, '*')].each do |path|
      repo_name = File.basename(path)

      if Dir.exist?(path) && extension?(repo_name)
        readme_path = File.join(path, 'README.md')
        content = File.read(readme_path)

        if !content[template]
          if !content.end_with?("\n")
            content << "\n"
          end

          content << template
          updated << repo_name

          File.open(readme_path, 'w') do |f|
            f.write(content)
          end
        end
      end
    end

    if updated.any?
      puts "updated: #{updated.join(' ')}"
    end
  end
end
