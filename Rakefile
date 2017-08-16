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

Dir['tasks/*.rake'].each { |r| import r }
