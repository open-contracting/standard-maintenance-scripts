require 'open-uri'
require 'set'

require 'colored'
require 'faraday'
require 'octokit'

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
  @repos ||= client.repos(organization, per_page: 100)
end

def extension?(name)
  name.end_with?('extension') || ['ocds_performance_failures', 'public-private-partnerships', 'trade'].include?(name)
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

namespace :repos do
  desc 'Lists repositories with multiple branches'
  task :many_branches do
    exclusions = Set.new((ENV['EXCLUDE'] || '').split(','))
    repos.each do |repo|
      branches = repo.rels[:branches].get.data.reject do |branch|
        branch.name == repo.default_branch || exclusions.include?(branch.name)
      end

      if branches.any?
        puts "#{repo.html_url}/branches"
        puts "  #{branches.size}: #{branches.map(&:name).join(' ')}"
      end
    end
  end

  desc 'Lists protected branches'
  task :protected_branches do
    repos.each do |repo|
      # TODO
      raise repo.rels[:branches].get(accept: 'application/vnd.github.loki-preview+json').data.inspect
    end
  end

  desc 'Lists descriptions'
  task :descriptions do
    repos.partition{ |repo| extension?(repo.name) }.each do |set|
      puts
      set.each do |repo|
        puts "#{repo.html_url}\n- #{repo.description}"
      end
    end
  end

  desc 'Lists non-default labels'
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

  desc 'Lints repositories'
  task :lint do
    repos.each do |repo|
      if repo.has_wiki
        response = Faraday.get("#{repo.html_url}/wiki")
        if response.status == 302 && response.headers['location'] == repo.html_url
          puts "Disable wiki #{repo.html_url}/settings"
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

  desc 'List repositories with number of issues, PRs, branches, milestones and whether wiki, pages, issues, projects are enabled'
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
