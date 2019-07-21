require 'bundler/setup'

require 'csv'
require 'fileutils'
require 'json'
require 'open-uri'
require 'pp'
require 'set'

require 'cld'
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

EXTERNAL_EXTENSIONS = [
  'CompraNet/ocds_releasePublisher_extension',
  'INAImexico/ocds_implementationStatus_extension',
]

REQUIRE_PULL_REQUEST_REVIEWS = [
  'kingfisher',
  'kingfisher-process',
  'kingfisher-scrape',
  'lib-cove-ocds',
]
ENFORCE_ADMINS = [
  'public-private-partnerships',
  'standard',
] + REQUIRE_PULL_REQUEST_REVIEWS

PROFILES = [
  'european-union',
  'government-procurement-agreement',
  'public-private-partnerships',
]
TEMPLATES = [
  'standard_extension_template',
  'standard_profile_template',
]

specifications = [
  'glossary',
  'infrastructure',
  'ocds-extensions',
  'standard',
]
guides = [
  'ocds-kibana-manual',
  'ocds-r-manual',
]
extension_tools = [
  'extension-explorer',
  'extension_creator',
  'extension_registry',
  'extension_registry.py',
  'ocds-extensions-translations',
]
internal_tools = [
  'european-union-support',
  'json-schema-random',
  'ocds-pdf',
  'standard-development-handbook',
  'standard-maintenance-scripts',
]
DOCUMENTATION_DEPENDENCIES = [
  'ocds-babel',
  'sphinxcontrib-opencontracting',
  'standard_theme',
]
LEGACY = [
  'open-contracting.github.io',
  'standard-legacy-staticsites',
]
non_tools = specifications + guides + DOCUMENTATION_DEPENDENCIES + LEGACY

REPOSITORY_CATEGORIES = {
  'Specifications' => -> (repo) { specifications.include?(repo.name) },
  'Guides' => -> (repo) { guides.include?(repo.name) },
  'Tools' => -> (repo) { !extension?(repo.name) && !extension_tools.include?(repo.name) && !internal_tools.include?(repo.name) && !non_tools.include?(repo.name) },
  'Extension tools' => -> (repo) { extension_tools.include?(repo.name) },
  'Internal tools' => -> (repo) { internal_tools.include?(repo.name) },
  'Documentation dependencies' => -> (repo) { DOCUMENTATION_DEPENDENCIES.include?(repo.name) },
  'Templates' => -> (repo) { template?(repo.name) },
  'Profiles' => -> (repo) { profile?(repo.name) },
  'Extensions' => -> (repo) { extension?(repo.name, profiles: false, templates: false) },
  'Legacy' => -> (repo) { LEGACY.include?(repo.name) },
}

TECH_SUPPORT_PRIORITIES = {
  # Specifications
  'glossary' => '✴️', # documentation support
  'infrastructure' => '✴️✴️', # sector documentation
  'ocds-extensions' => ' ', # issues only
  'standard' => '✴️✴️✴️', # core documentation

  # Guides
  'ocds-kibana-manual' => ' ',
  'ocds-r-manual' => ' ',

  # Tools
  'lib-cove-ocds' => '✴️✴️✴️', # implementation step
  'kingfisher' => '✴️', # key tool
  'kingfisher-archive' => ' ',
  'kingfisher-colab' => ' ',
  'kingfisher-process' => '✴️', # key tool
  'kingfisher-scrape' => '✴️', # key tool
  'kingfisher-views' => ' ',
  'ocds-merge' => '✴️✴️', # reference implementation
  'ocds-show' => ' ', # infrequently used
  'ocds-show-ppp' => ' ', # infrequently used
  'ocdskit' => '✴️', # key tool
  'ocdskit-web' => ' ',
  'sample-data' => '✴️', # frequently used

  # Extension tools
  'extension-explorer' => '✴️✴️', # extensions documentation
  'extension_creator' => ' ', # infrequently used
  'extension_registry' => '✴️✴️', # authoritative resource
  'extension_registry.py' => '✴️✴️', # frequent dependency
  'ocds-extensions-translations' => '✴️✴️', # extensions documentation

  # Internal tools
  'european-union-support' => ' ', # scratch pad
  'json-schema-random' => ' ', # infrequently used
  'ocds-pdf' => ' ', # alpha
  'standard-development-handbook' => '✴️', # key internal documentation
  'standard-maintenance-scripts' => '✴️', # internal quality assurance

  # Templates
  'standard_extension_template' => '✴️', # public template
  'standard_profile_template' => ' ', # internal template
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
    elsif ENV['ORG']
      [ENV['ORG']]
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

def read_github_file(repo, path)
  Base64.decode64(client.contents(repo, path: path).content)
end

def profile?(name)
  PROFILES.include?(name)
end

def template?(name)
  TEMPLATES.include?(name)
end

def extension?(name, profiles: true, templates: true)
  name.start_with?('ocds_') && name.end_with?('_extension') || profiles && profile?(name) || templates && template?(name)
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
      if ['bitbucket.org', 'raw.githubusercontent.com'].include?(parts.hostname)
        ids_to_repos[version.fetch('Id')] = parts.path.split('/')[1..2].join('/')
      else
        raise "#{parts.hostname} not supported (#{version['Id']})"
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
  url = 'https://standard.open-contracting.org/extension_registry/master/extensions.json'
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
