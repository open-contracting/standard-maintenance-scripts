require 'bundler/setup'

require 'csv'
require 'fileutils'
require 'json'
require 'open-uri'
require 'pp'
require 'set'

require 'colored'
require 'faraday'
require 'google/apis/drive_v2'
require 'googleauth'
require 'googleauth/stores/file_token_store'
require 'hashdiff'
require 'htmlentities'
require 'mail'
require 'nokogiri'
require 'octokit'
require 'safe_yaml'

SafeYAML::OPTIONS[:default_mode] = :safe

OTHER_EXTENSIONS = ['api_extension', 'ocds_performance_failures']
OTHER_PROFILES = ['public-private-partnerships']
TEMPLATES = ['standard_extension_template', 'standard_profile_template']

# See https://developers.google.com/drive/v2/web/quickstart/ruby
OOB_URI = 'urn:ietf:wg:oauth:2.0:oob'
APPLICATION_NAME = 'Drive API Ruby Quickstart'
CLIENT_SECRETS_PATH = 'client_secret.json'
CREDENTIALS_PATH = File.join(Dir.home, '.credentials', 'drive-ruby-quickstart.yaml')
SCOPE = Google::Apis::DriveV2::AUTH_DRIVE_METADATA_READONLY

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

def service
  @service ||= begin
    service = Google::Apis::DriveV2::DriveService.new
    service.client_options.application_name = APPLICATION_NAME
    service.authorization = authorize
    service
  end
end

def organizations
  @organizations ||= begin
    if ENV['ORGS']
      ENV['ORGS'].split(',')
    else
      ['open-contracting', 'open-contracting-extensions']
    end
  end
end

def repos
  @repos ||= begin
    organizations.reduce([]) do |memo, organization|
      repos = client.repos(organization, per_page: 100, accept: 'application/vnd.github.drax-preview+json') # licenses
      if ENV['REPOS']
        memo + repos.select{ |repo| ENV['REPOS'].include?(repo.name) }
      else
        memo + repos
      end
    end
  end
end

def profile?(name)
  name.start_with?('ocds-for-') || OTHER_PROFILES.include?(name)
end

def extension?(name, profiles: true, templates: true)
  # This should match the logic in `test_json.py`.
  name.start_with?('ocds') && name.end_with?('extension') || OTHER_EXTENSIONS.include?(name) || profiles && profile?(name) || templates && TEMPLATES.include?(name)
end

def variables(*keys)
  keys.map do |key|
    value = ENV[key]
    if value.nil? || value.empty?
      abort "usage: rake #{ARGV[0]} #{keys.map{ |key| "#{key}=value" }.join(' ')}"
    end
    value
  end
end

def core_extensions
  @core_extensions ||= begin
    base_url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/'

    ids_to_repos = {}
    CSV.parse(open("#{base_url}/extension_versions.csv").read, headers: true).each do |version|
      parts = URI.parse(version.fetch('Base URL'))
      # Assumes different versions of the same extension use the same repository.
      if parts.hostname == 'raw.githubusercontent.com'
        ids_to_repos[version.fetch('Id')] = parts.path.split('/')[1..2].join('/')
      else
        raise "#{parts.hostname} not supported"
      end
    end

    repos_to_core = {}
    CSV.parse(open("#{base_url}/extensions.csv").read, headers: true).each do |extension|
      repos_to_core[ids_to_repos.fetch(extension.fetch('Id'))] = extension.fetch('Core') == 'true'
    end

    repos_to_core
  end
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
