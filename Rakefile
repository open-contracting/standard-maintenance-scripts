require 'bundler/setup'

require 'json'
require 'open-uri'
require 'set'

require 'colored'
require 'faraday'
require 'hashdiff'
require 'octokit'
require 'safe_yaml'

SafeYAML::OPTIONS[:default_mode] = :safe

def s(condition)
  condition && 'Y'.green || 'N'.blue
end

def i(integer)
  integer.nonzero? && integer.to_s.green || integer.to_s.blue
end

def client
  @client ||= begin
    client = Octokit::Client.new(netrc: true)
    client.login
    client
  end
end

def organization
  @organization ||= ENV['ORG'] || 'open-contracting'
end

def repos
  @repos ||= client.repos(organization, per_page: 100, accept: 'application/vnd.github.drax-preview+json')
end

def extension?(name)
  name.end_with?('extension') || ['ocds_performance_failures', 'public-private-partnerships', 'trade'].include?(name)
end

desc 'Report which non-extension repositories are not cloned'
task :uncloned do
  extension_repositories = Set.new
  url = 'http://standard.open-contracting.org/extension_registry/master/extensions.json'
  JSON.load(open(url).read).fetch('extensions').each do |extension|
    if extension.fetch('active')
      extension_repositories << URI.parse(extension['url']).path.split('/')[2]
    end
  end

  cloned_repositories = Set.new(Dir['../*'].map{ |path| File.basename(path) })

  repos.each do |repo|
    if !extension_repositories.include?(repo.name) && !cloned_repositories.include?(repo.name)
      suffix = ''
      if repo.language
        suffix << " #{repo.language.bold}"
      end
      puts "#{repo.html_url}#{suffix}"
    end
  end
end

namespace :org do
  desc 'Lists organization members'
  task :members do
    # Last updated 2017-08-14
    known_members = [
      # Open Contracting Partnership
      # https://www.open-contracting.org/about/team/
      'jpmckinney', # James McKinney
      'lindseyam', # Lindsey Marchessault

      # Open Data Services Co-op
      # http://opendataservices.coop
      'bjwebb', # Ben Webb
      'caprenter', # David Carpenter
      'duncandewhurst', # Duncan Dewhurst
      'edugomez', # Eduardo Gomez
      'julijahansen', # Julija Hansen
      'kindly', # David Raznick
      'robredpath', # Rob Redpath
      'timgdavies', # Tim Davies

      # Iniciativa Latinoamericana por los Datos Abiertos
      # https://idatosabiertos.org/acerca-de-nosotros/
      'cdemidchuk', # Catalina Demidchuk
      'emanuelzh', # Emanuel Zámano
      'juanpane', # Juan Pane
      'scrollif', # Fabrizio Scrollini
      'tlacoyodefrijol', # Oscar Montiel
      'yolile', # Yohanna Lisnichuk
    ]

    people = client.org_members(organization) + client.org_invitations(organization, accept: 'application/vnd.github.korra-preview')

    puts people.map{ |member| member.login.downcase } - known_members
  end
end

namespace :pulls do
  desc 'Creates pull requests from a given branch'
  task :create do
    ref = ENV['REF']
    if ref.nil?
      abort 'usage: rake pulls:create REF=branch'
    end

    repos.each do |repo|
      if repo.rels[:pulls].get.data.none?{ |pull| pull.head.ref == ref }
        branch = repo.rels[:branches].get.data.find{ |branch| branch.name == ref }
        if branch
          title = client.commit(repo.full_name, branch.commit.sha).commit.message
          pull = client.create_pull_request(repo.full_name, repo.default_branch, ref, title)
          puts "#{pull.html_url} #{title.bold}"
        end
      end
    end
  end

  desc 'Merges pull requests for a given branch'
  task :merge do
    ref = ENV['REF']
    if ref.nil?
      abort 'usage: rake pulls:merge REF=branchtomerge'
    end

    repos.each do |repo|
      repo.rels[:pulls].get.data.each do |pull|
        if pull.head.ref == ref
          client.merge_pull_request(repo.full_name, pull.number)
          puts pull.html_url
        end
      end
    end
  end
end

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
    repos.each do |repo|
      headers = {accept: 'application/vnd.github.loki-preview+json'}
      branches = repo.rels[:branches].get(headers: headers).data
      default_branch = branches.find{ |branch| branch.name == repo.default_branch }
      contexts = []

      if repo.rels[:hooks].get.data.any?{ |datum| datum.name == 'travis' }
        contexts << 'continuous-integration/travis-ci'
      end

      options = headers.merge(enforce_admins: true, required_status_checks: {strict: true, contexts: contexts})
      if !default_branch.protected
        client.protect_branch(repo.full_name, default_branch.name, options)
        puts "#{repo.html_url}/settings/branches/#{default_branch.name} protected"
      elsif default_branch.protection.enabled && default_branch.protection.required_status_checks.enforcement_level == 'everyone' && default_branch.protection.required_status_checks.contexts.empty? && default_branch.protection.required_status_checks.contexts != contexts
        client.protect_branch(repo.full_name, default_branch.name, options)
        puts "#{repo.html_url}/settings/branches/#{default_branch.name} added: #{contexts.join(', ')}"
      elsif !default_branch.protection.enabled || default_branch.protection.required_status_checks.enforcement_level != 'everyone' || default_branch.protection.required_status_checks.contexts != contexts
        puts "#{repo.html_url}/settings/branches/#{default_branch.name} unexpectedly configured"
      end

      protected_branches = branches.select{ |branch| branch.name != repo.default_branch && branch.protected }
      if protected_branches.any?
        puts "#{repo.html_url}/settings/branches unexpectedly protects:" 
        protected_branches.each do |branch|
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
