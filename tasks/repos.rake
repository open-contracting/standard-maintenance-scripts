namespace :repos do
  def non_default_or_pull_or_upstream_or_excluded_branches(repo)
    exclusions = Set.new((ENV['EXCLUDE'] || '').split(','))

    pulls = repo.rels[:pulls].get.data.map{ |pull| pull.head.ref }

    # In forks, we maintain a reference to the upstream master branch.
    if repo.fork && %w(open_contracting opencontracting).include?(repo.default_branch)
      exclusions << 'master'
    end

    # Exceptions for `extension_registry`.
    if repo.name == 'extension_registry'
      exclusions << 'ppp'
      pattern = /\Av\d(?:\.\d){1,}\z/
    else
      pattern = /\A\z/
    end

    repo.rels[:branches].get.data.reject do |branch|
      branch.name == repo.default_branch || pulls.include?(branch.name) || branch.name[pattern] || exclusions.include?(branch.name)
    end
  end

  desc 'Regenerates the badges pages'
  task :badges do
    output = [
      '# Project Build and Dependency Status',
    ]

    repos.partition{ |repo| !extension?(repo.name) }.each_with_index do |set, index|
      output << ''

      if index.zero?
        output << "## Repositories"
      else
        output << "## Extensions"
      end

      output += [
        '',
        'Name|Build|Dependencies',
        '-|-|-',
      ]

      set.each do |repo|
        hooks = repo.rels[:hooks].get.data

        line = "[#{repo.name}](#{repo.html_url})|"

        hook = hooks.find{ |datum| datum.name == 'travis' }
        if hook && hook.active
          line << "[![Build Status](https://travis-ci.org/#{repo.full_name}.svg)](https://travis-ci.org/#{repo.full_name})"
        end

        line << '|'

        hook = hooks.find{ |datum| datum.config.url == 'https://requires.io/github/web-hook/' }
        if hook && hook.active
          line << "[![Requirements Status](https://requires.io/github/#{repo.full_name}/requirements.svg)](https://requires.io/github/#{repo.full_name}/requirements/)"
        end

        output << line

        print '.'
      end
    end

    File.open('badges.md', 'w') do |f|
      f.write(output.join("\n"))
    end
  end

  desc 'Checks Travis configurations'
  task :travis do
    def read(repo, path)
      Base64.decode64(client.contents(repo, path: path).content)
    end

    expected = read('open-contracting/standard-maintenance-scripts', 'fixtures/.travis.yml')

    repos.each do |repo|
      hook = repo.rels[:hooks].get.data.find{ |datum| datum.name == 'travis' }
      if hook && hook.active
        begin
          actual = read(repo.full_name, '.travis.yml')
          if actual != expected
            diff = HashDiff.diff(YAML.load(actual), YAML.load(expected))
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
      if extension?(repo.name) && !Base64.decode64(client.readme(repo.full_name).content)[template]
        puts "#{repo.html_url}#readme #{'missing content'.bold}"
      end
    end
  end

  desc 'Lists missing or unexpected licenses'
  task :licenses do
    repos.partition{ |repo| extension?(repo.name) }.each do |set|
      puts
      set.each do |repo|
        # The following licenses are acceptable:
        # * Apache 2.0 for extensions and documentation
        # * BSD 3-Clause for Python
        # * MIT for CSS, JavaScript and Ruby
        unless repo.license && (
          repo.license.key == 'apache-2.0' && [nil, 'Python'].include?(repo.language) ||
          repo.license.key == 'bsd-3-clause' && repo.language == 'Python' ||
          repo.license.key == 'mit' && ['CSS', 'JavaScript', 'Ruby'].include?(repo.language)
        )
          line = repo.html_url
          if repo.license
            line << " #{repo.license.key.bold}"
          else
            line << " #{'missing'.bold}"
          end
          if repo.language
            line << " (#{repo.language})"
          end
          puts line
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
      labels = repo.rels[:labels].get.data.map(&:name)
      if labels & default_labels == default_labels
        labels -= default_labels
      end
      if labels.any?
        puts "#{repo.html_url}/labels"
        labels.each do |label|
          puts "- #{label}"
        end
      end
    end
  end

  desc 'Lists non-extension releases'
  task :releases do
    expected_extension_tags = Set.new(['ppp', 'v1.1', 'v1.1.1'])

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

  desc 'Lists non-Travis, non-Requires.io webhooks'
  task :webhooks do
    repos.each do |repo|
      data = repo.rels[:hooks].get.data.reject{ |datum| datum.name == 'travis' || datum.config.url == 'https://requires.io/github/web-hook/' }
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
    format = '%-50s  %12s  %11s  %11s  %11s  %s  %s  %s  %s  %s'

    repos.partition{ |repo| extension?(repo.name) }.each do |set|
      # Number of open issues
      # Number of open pull requests
      # Number of branches, excluding default, pull, upstream, excluded branches
      # Number of open milestones
      # Whether the repo has a wiki
      # Whether the repo has GitHub Pages
      # Whether the repo has issues enabled
      # Whether the repo has projects enabled
      # The top contributor (e.g. to decide who to contact)
      puts '%-50s   %s  %s  %s  %s  %s  %s  %s  %s  %s' % ['', '#I', '#P', '#B', '#M', 'W', 'P', 'I', 'P', 'C']

      set.sort{ |a, b|
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

        puts format % [
          repo.name,
          i(repo.open_issues - pull_requests),
          i(pull_requests),
          i(non_default_or_pull_or_upstream_or_excluded_branches(repo).size),
          i(repo.rels[:milestones].get.data.size),
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
      data[repo.name] = client.views(repo.full_name, per: 'week', accept: 'application/vnd.github.spiderman-preview')
    end

    data.sort{ |a, b|
      if a[1].uniques == b[1].uniques
        b[1].count <=> a[1].count
      else
        b[1].uniques <=> a[1].uniques
      end
    }.partition{ |name, _| extension?(name) }.each do |set|
      puts
      set.each do |name, datum|
        puts '%-45s %2d uniques %3d views' % [name, datum.uniques, datum.count]
      end
    end
  end
end
