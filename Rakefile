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

OTHER_EXTENSIONS = [
  'api_extension',
  'ocds_performance_failures',
]
PROFILES = [
  'european-union',
  'government-procurement-agreement',
  'public-private-partnerships',
]
TEMPLATES = [
  'standard_extension_template',
  'standard_profile_template',
]

extension_tools = [
  'extension-explorer',
  'extensions-data-collector',
  'extension_creator',
  'extension_registry.py',
]
documentation_dependencies = [
  'ocds-babel',
  'sphinxcontrib-opencontracting',
  'standard_theme',
]
miscellaneous_repositories = [
  'api-specification',
  'extension_registry',
  'glossary',
  'infrastructure',
  'ocds-extensions',
  'standard',
]
legacy = [
  'open-contracting.github.io',
  'standard-legacy-staticsites',
]
non_tools = documentation_dependencies + miscellaneous_repositories + legacy

REPOSITORY_CATEGORIES = {
  'Tools' => -> (repo) { !extension?(repo.name) && !non_tools.include?(repo.name) },
  'Extension tools' => -> (repo) { extension_tools.include?(repo.name) },
  'Documentation dependencies' => -> (repo) { documentation_dependencies.include?(repo.name) },
  'Miscellaneous repositories' => -> (repo) { miscellaneous_repositories.include?(repo.name) },
  'Templates' => -> (repo) { template?(repo.name) },
  'Profiles' => -> (repo) { profile?(repo.name) },
  'Extensions' => -> (repo) { extension?(repo.name, profiles: false, templates: false) },
  'Legacy' => -> (repo) { legacy.include?(repo.name) },
}

TECH_SUPPORT_PRIORITIES = {
  # Tools
  'json-schema-random' => ['low'],
  'lib-cove-ocds' => ['-'],
  'kingfisher' => ['medium', 'key tool'],
  'ocds-faker' => ['low'],
  'ocds-merge' => ['high', 'reference implementation for merging releases'],
  'ocds-show' => ['low'],
  'ocds-show-ppp' => ['low'],
  'ocdskit' => ['medium', 'key tool'],
  'sample-data' => ['medium', 'key resource, frequently visited'],
  'standard-development-handbook' => ['medium', 'internal, key documentation'],
  'standard-maintenance-scripts' => ['medium', 'internal, quality assurance'],
  # Extension tools
  'extension-explorer' => ['high', 'extensions documentation'],
  'extensions-data-collector' => ['-'],
  'extension_creator' => ['low'],
  'extension_registry.py' => ['high', 'common dependency'],
  # Documentation dependencies
  'ocds-babel' => ['high', 'dependency of `standard` and profiles'],
  'standard_theme' => ['high', 'dependency of `standard` and profiles'],
  'sphinxcontrib-opencontracting' => ['high', 'dependency of `standard`'],
  # Miscellaneous repositories
  'api-specification' => ['low', 'draft'],
  'european-union-support' => ['low', 'scratch pad'],
  'extension_registry' => ['high', 'authoritative resource'],
  'glossary' => ['medium', 'potential future key resource'],
  'infrastructure' => ['high'],
  'ocds-extensions' => ['-'],
  'standard' => ['high', 'core documentation'],
  # Templates
  'standard_extension_template' => ['medium', 'public resource'],
  'standard_profile_template' => ['low', 'internal template'],
  # Legacy
  'open-contracting.github.io' => ['low'],
  'standard-legacy-staticsites' => ['low'],
}

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

# See https://developers.google.com/drive/v2/web/quickstart/ruby
def authorize
  credentials_path = File.join(Dir.home, '.credentials', 'drive-ruby-quickstart.yaml')

  FileUtils.mkdir_p(File.dirname(credentials_path))

  client_id = Google::Auth::ClientId.from_file('client_secret.json')
  token_store = Google::Auth::Stores::FileTokenStore.new(file: credentials_path)
  authorizer = Google::Auth::UserAuthorizer.new(client_id, Google::Apis::DriveV2::AUTH_DRIVE_METADATA_READONLY, token_store)
  user_id = 'default'
  credentials = authorizer.get_credentials(user_id)

  if credentials.nil?
    puts 'Open the following URL in the browser and enter the resulting code after authorization'
    oob_uri = 'urn:ietf:wg:oauth:2.0:oob'
    puts authorizer.get_authorization_url(base_url: oob_uri)
    code = gets
    credentials = authorizer.get_and_store_credentials_from_code(user_id: user_id, code: code, base_url: oob_uri)
  end

  credentials
end

def service
  @service ||= begin
    service = Google::Apis::DriveV2::DriveService.new
    service.client_options.application_name = 'Drive API Ruby Quickstart'
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
  PROFILES.include?(name)
end

def template?(name)
  TEMPLATES.include?(name)
end

def extension?(name, profiles: true, templates: true)
  name.start_with?('ocds') && name.end_with?('extension') || OTHER_EXTENSIONS.include?(name) || profiles && profile?(name) || templates && template?(name)
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
