require 'open-uri'

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

def repos
  @repos ||= client.repos('open-contracting', per_page: 100)
end

desc 'Lists repositories with multiple branches'
task :many_branches do
  repos.each do |repo|
    branches = repo.rels[:branches].get.data.reject do |branch|
      branch.name == repo.default_branch
    end

    if branches.any?
      puts "#{repo.html_url}/branches"
      puts "  #{branches.size}: #{branches.map(&:name).join(' ')}"
    end
  end
end

desc 'Lists repositories with empty wikis'
task :empty_wikis do
  repos.each do |repo|
    if repo.has_wiki
      response = Faraday.get("#{repo.html_url}/wiki")

      if response.status == 302 && response.headers['location'] == repo.html_url
        puts "#{repo.html_url}/settings"
      end
    end
  end
end

desc 'List repositories with number of open issues, open PRs, issues enabled, wiki enabled, pages enabled'
task :status do
  format = '%-50s  %11s  %11s  %11s  %s  %s  %s'

  puts '%-50s  %s  %s  %s  %s  %s  %s' % ['', '#I', '#P', '#M', 'I', 'W', 'P']

  repos.sort{ |a, b|
    if a.open_issues == b.open_issues
      a.name <=> b.name
    else
      a.open_issues <=> b.open_issues
    end
  }.each do |repo|
    puts format % [
      repo.name,
      i(repo.open_issues),
      i(repo.rels[:pulls].get.data.size),
      i(repo.rels[:milestones].get.data.size),
      s(repo.has_issues),
      s(repo.has_wiki),
      s(repo.has_pages),
    ]
  end
end
