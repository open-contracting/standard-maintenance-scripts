require 'hashdiff'

namespace :repos do
  def s(condition)
    condition && 'Y'.green || 'N'.blue
  end

  def i(integer)
    integer.nonzero? && integer.to_s.green || integer.to_s.blue
  end

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

  desc 'Lists open and dismissed vulnerabilities'
  task :vulnerabilities do
    repos.each do |repo|
      params = {
        query: %({
          repository(name: "#{repo.name}", owner: "#{repo.owner.login}") {
            vulnerabilityAlerts(first: 100) {
              nodes {
                createdAt
                dismissedAt
                securityVulnerability {
                  package {
                    name
                  }
                }
              }
            }
          }
        })
      }
      response = Faraday.post('https://api.github.com/graphql', JSON.dump(params)) do |request|
        request.headers['Authorization'] = "bearer #{ENV.fetch('GITHUB_ACCESS_TOKEN')}"
      end
      data = JSON.load(response.body)
      if data['data']['repository']['vulnerabilityAlerts']['nodes'].any?
        puts "#{repo.full_name}"
        rows = data['data']['repository']['vulnerabilityAlerts']['nodes'].map do |node|
          [node['securityVulnerability']['package']['name'], node['dismissedAt']]
        end
        rows.uniq.each do |package_name, dismissed_at|
          puts "- #{package_name} #{dismissed_at}"
        end
      end
    end
  end

  desc 'Lists repositories with missing or unexpected continuous integration configuration'
  task :ci do
    expected = read_github_file('open-contracting/standard-maintenance-scripts', 'fixtures/lint.yml')

    repos.each do |repo|
      actual = read_github_file(repo.full_name, '.github/workflows/lint.yml')
      if actual.empty?
        actual = read_github_file(repo.full_name, '.github/workflows/ci.yml')
      end
      if !actual.empty? && actual != expected
        diff = Hashdiff.diff(YAML.load(expected), YAML.load(actual))
        if diff.any?
          puts "#{repo.html_url}/blob/#{repo.default_branch}/.github/workflows #{'changes configuration'.bold}"
        end
        PP.pp(diff, $>, 120)
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

  desc 'Lists secrets'
  task :secrets do
    repos.each do |repo|
      data = client.list_secrets(repo.full_name).secrets.map(&:name)
      # Ignore OCDS documentation secrets.
      if data.any? && data != ['ELASTICSEARCH_PASSWORD', 'PRIVATE_KEY']
        puts "#{repo.html_url}/settings/secrets/actions"
        data.each do |datum|
          puts "- #{datum}"
        end
      end
    end
  end

  desc 'Lists non-ReadTheDocs webhooks'
  task :webhooks do
    repos.each do |repo|
      data = repo.rels[:hooks].get.data.reject do |datum|
        datum.config.url[%r{\A(https://readthedocs.org/api/v2/webhook/)}]
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
    format = '%-110s  %12s  %11s  %11s  %11s  %11s  %s  %s  %s  %s  %s'

    REPOSITORY_CATEGORIES.each do |heading, condition|
      puts

      # Number of open [I]ssues
      # Number of open [P]ull requests
      # Number of [B]ranches, excluding default, pull, upstream, excluded branches
      # Number of open [M]ilestones
      # Number of open p[R]ojects
      # Whether the repo has a [W]iki
      # Whether the repo has GitHub [P]ages
      # Whether the repo has [I]ssues enabled
      # Whether the repo has [P]rojects enabled
      # The top contributor (e.g. to decide who to contact)
      puts '%-110s   %s  %s  %s  %s  %s  %s  %s  %s  %s  %s' % [heading.upcase, '#I', '#P', '#B', '#M', '#R', 'W', 'P', 'I', 'P', 'C']

      repos.select(&condition).sort{ |a, b|
        if a.open_issues == b.open_issues
          a.name <=> b.name
        else
          a.open_issues <=> b.open_issues
        end
      }.each do |repo|
        if repo.archived
          next
        end

        pull_requests = repo.rels[:pulls].get.data.size

        top_contributor = repo.rels[:contributors].get.data
        if top_contributor.empty?
          # Occurs if the repository has no commits.
          top_contributor = nil
        else
          # At time of writing, I'm the top contributor on most repositories, which is not useful information.
          top_contributor = repo.rels[:contributors].get.data.find{ |contributor| contributor.login != 'jpmckinney' }
        end

        if repo.has_projects
          projects = client.projects(repo.full_name, accept: 'application/vnd.github.inertia-preview+json').size # projects
        else
          projects = 0
        end

        puts format % [
          "#{repo.html_url}/issues",
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
        puts '%-45s %3d uniques %3d views' % [name, datum.uniques, datum.count]
      end
    end
  end
end
