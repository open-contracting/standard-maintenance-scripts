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

  desc 'Checks Travis configurations'
  task :travis do
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
              puts "#{repo.html_url}/blob/#{repo.default_branch}/.travis.yml #{'lacks configuration'.bold}"
            end
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
      if extension?(repo.name) && !client.readme(repo.full_name)[template]
        puts "#{repo.html_url}#readme #{'missing content'.bold}"
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
          i(non_default_or_pull_or_upstream_or_excluded_branches(repo).size),
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
