namespace :repos do
  def non_default_or_pull_or_upstream_or_excluded_branches(repo)
    exclusions = Set.new((ENV['EXCLUDE'] || '').split(','))

    pulls = repo.rels[:pulls].get.data.map{ |pull| pull.head.ref }

    # In forks, we maintain a reference to the upstream master branch.
    if repo.fork && %w(open_contracting opencontracting).include?(repo.default_branch)
      exclusions << 'master'
    end

    repo.rels[:branches].get.data.reject do |branch|
      branch.name == repo.default_branch || pulls.include?(branch.name) || exclusions.include?(branch.name)
    end
  end

  desc 'Lists repositories with missing or unexpected Travis configuration'
  task :travis do
    expected = read_github_file('open-contracting/standard-maintenance-scripts', 'fixtures/.travis.yml')

    repos.each do |repo|
      hook = repo.rels[:hooks].get.data.find{ |datum| datum.name == 'travis' || datum.config.url == 'https://notify.travis-ci.org' }
      if hook
        begin
          actual = read_github_file(repo.full_name, '.travis.yml')
          if actual != expected
            diff = Hashdiff.diff(YAML.load(actual), YAML.load(expected))
            if diff.any?
              puts "#{repo.html_url}/blob/#{repo.default_branch}/.travis.yml #{'changes configuration'.bold}"
            end
            PP.pp(diff, $>, 120)
          end
        rescue Octokit::NotFound
          puts "#{repo.html_url} #{'lacks .travis.yml'.bold}"
        end
      else
        puts "#{repo.html_url} #{'lacks Travis'.bold}"
      end
    end
  end

  desc 'Lists repositories with unexpected, old branches'
  task :branches do
    repos.each do |repo|
      branches = non_default_or_pull_or_upstream_or_excluded_branches(repo)

      if branches.any?
        puts "#{repo.html_url}/branches"
        puts "  #{branches.size}: #{branches.map(&:name).join(' ')}"
      end
    end
  end

  desc 'Lists extension repositories with missing template content'
  task :readmes do
    template = <<-END
## Issues

Report issues for this extension in the [ocds-extensions repository](https://github.com/open-contracting/ocds-extensions/issues), putting the extension's name in the issue's title.
    END

    repos.each do |repo|
      if extension?(repo.name, profiles: false, templates: false) && !Base64.decode64(client.readme(repo.full_name).content)[template]
        puts "#{repo.html_url}#readme #{'missing content'.bold}"
      end
    end
  end

  desc 'Lists missing or unexpected licenses'
  task :licenses do
    repos.partition{ |repo| extension?(repo.name) }.each_with_index do |set, i|
      puts
      licenses = {}
      set.each do |repo|
        license = repo.license&.key.to_s
        language = repo.language.to_s
        licenses[license] ||= {}
        licenses[license][language] ||= []
        licenses[license][language] << repo.html_url
      end

      licenses.sort.each do |license, languages|
        # Extensions, profiles and templates are expected to be Apache 2.0.
        if i.zero? && license == 'apache-2.0'
          next
        end

        if license.empty?
          puts 'missing'.bold
        else
          puts license.bold
        end

        languages.sort.each do |language, repos|
          # JavaScript and Ruby are expected to be MIT. Python is expected to be BSD 3-Clause.
          if i.nonzero? && (license == 'mit' && %w(JavaScript Ruby).include?(language) || license == 'bsd-3-clause' && language == 'Python')
            next
          end

          repos.each do |html_url|
            line = html_url
            if !language.empty?
              line << " (#{language})"
            end
            puts line
          end
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

  desc 'Lists non-extension releases'
  task :releases do
    expected_extension_tags = Set.new(['ppp', 'v1.1', 'v1.1.1', 'v1.1.3', 'v1.1.4'])

    repos.each do |repo|
      data = repo.rels[:releases].get.data
      if extension?(repo.name)
        data.reject!{ |datum| expected_extension_tags.include?(datum.tag_name) }
      end
      if data.any?
        puts "#{repo.html_url}/releases"
        data.each do |datum|
          puts "- #{datum.tag_name}: #{datum.name}"
        end
      end
    end
  end

  desc 'Lists non-Travis, non-ReadTheDocs webhooks'
  task :webhooks do
    repos.each do |repo|
      # Support both GitHub Services and GitHub Apps until GitHub Services fully retired.
      data = repo.rels[:hooks].get.data.reject do |datum|
        datum.name == 'travis' || datum.config.url == 'https://notify.travis-ci.org' || datum.config.url[%r{\Ahttps://readthedocs.org/api/v2/webhook/}]
      end
      if data.any?
        puts "#{repo.html_url}/settings/hooks"
        data.each do |datum|
          puts "- #{datum.name} #{datum.config.url}"
        end
      end
    end
  end

  desc 'Lists repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled'
  task :status do
    format = '%-50s  %12s  %11s  %11s  %11s  %11s  %s  %s  %s  %s  %s'

    REPOSITORY_CATEGORIES.each do |heading, condition|
      puts

      # Number of open issues
      # Number of open pull requests
      # Number of branches, excluding default, pull, upstream, excluded branches
      # Number of open milestones
      # Number of open projects
      # Whether the repo has a wiki
      # Whether the repo has GitHub Pages
      # Whether the repo has issues enabled
      # Whether the repo has projects enabled
      # The top contributor (e.g. to decide who to contact)
      puts '%-50s   %s  %s  %s  %s  %s  %s  %s  %s  %s  %s' % [heading.upcase, '#I', '#P', '#B', '#M', '#R', 'W', 'P', 'I', 'P', 'C']

      repos.select(&condition).sort{ |a, b|
        if a.open_issues == b.open_issues
          a.name <=> b.name
        else
          a.open_issues <=> b.open_issues
        end
      }.each do |repo|
        pull_requests = repo.rels[:pulls].get.data.size
        # At time of writing, I'm the top contributor on most repositories (due
        # to widespread cleanup work), which is not useful information.
        top_contributor = repo.rels[:contributors].get.data.find{ |contributor| contributor.login != 'jpmckinney' }

        if repo.has_projects
          projects = client.projects(repo.full_name, accept: 'application/vnd.github.inertia-preview+json').size # projects
        else
          projects = 0
        end

        puts format % [
          repo.name,
          i(repo.open_issues - pull_requests),
          i(pull_requests),
          i(non_default_or_pull_or_upstream_or_excluded_branches(repo).size),
          i(repo.rels[:milestones].get.data.size),
          i(projects),
          s(repo.has_wiki),
          s(repo.has_pages),
          s(repo.has_issues),
          s(repo.has_projects),
          top_contributor && top_contributor.login,
        ]
      end
    end
  end

  desc 'Lists web traffic statistics over past two weeks'
  task :traffic do
    data = {}

    repos.each do |repo|
      data[repo.name] = client.views(repo.full_name, per: 'week', accept: 'application/vnd.github.spiderman-preview') # traffic
    end

    data.sort{ |a, b|
      if a[1].uniques == b[1].uniques
        b[1].count <=> a[1].count
      else
        b[1].uniques <=> a[1].uniques
      end
    }.partition{ |name, _| !extension?(name) }.each do |set|
      puts
      set.each do |name, datum|
        puts '%-45s %2d uniques %3d views' % [name, datum.uniques, datum.count]
      end
    end
  end
end
