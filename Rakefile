require 'bundler/setup'

require 'csv'
require 'fileutils'
require 'json'
require 'open-uri'
require 'pp'
require 'set'

require 'colored'
require 'faraday'
require 'octokit'
require 'safe_yaml'

SafeYAML::OPTIONS[:default_mode] = :safe

PROFILES = [
  'eforms',
  'european-union',
  'government-procurement-agreement',
  'public-private-partnerships',
]
TEMPLATES = [
  'standard_extension_template',
  'standard_profile_template',
]
SPECIFICATIONS = [
  'infrastructure',
  'ocds-extensions',
  'standard',
]

guides = [
  'ocds-kibana-manual',
  'ocds-r-manual',
  'sample-data',
]
extension_tools = [
  'extension-explorer',
  'extension_creator',
  'extension_registry',
  'extension_registry.py',
  'ocds-extensions-translations',
]
internal_tools = [
  'collect-generic',
  'data-support',
  'deploy',
  'editor-tools',
  'field-level-mapping-template',
  'jscc',
  'json-schema-random',
  'notebooks-ocds',
  'notebooks-oc4ids',
  'scrapy-log-analyzer',
  'software-development-handbook',
  'standard-development-handbook',
  'standard-maintenance-scripts',
  'yapw',
]
DOCUMENTATION_DEPENDENCIES = [
  'docson',
  'european-union-support',
  'ocds-babel',
  'ocds-index',
  'sphinxcontrib-opencontracting',
  'standard_theme',
]
non_tools = SPECIFICATIONS + guides + DOCUMENTATION_DEPENDENCIES

REPOSITORY_CATEGORIES = {
  'Specifications' => -> (repo) { specification?(repo.name) },
  'Guides' => -> (repo) { guides.include?(repo.name) },
  'Tools' => -> (repo) { !extension?(repo.name) && !extension_tools.include?(repo.name) && !internal_tools.include?(repo.name) && !non_tools.include?(repo.name) },
  'Extension tools' => -> (repo) { extension_tools.include?(repo.name) },
  'Internal tools' => -> (repo) { internal_tools.include?(repo.name) },
  'Documentation dependencies' => -> (repo) { DOCUMENTATION_DEPENDENCIES.include?(repo.name) },
  'Templates' => -> (repo) { template?(repo.name) },
  'Profiles' => -> (repo) { profile?(repo.name) },
  'Extensions' => -> (repo) { extension?(repo.name, profiles: false, templates: false) },
}

def client
  @client ||= begin
    client = Octokit::Client.new(netrc: true)
    client.login
    client
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
      repos = client.org_repos(organization, per_page: 100, accept: 'application/vnd.github.drax-preview+json') # licenses
      if ENV['REPOS']
        memo + repos.select{ |repo| ENV['REPOS'].split(',').include?(repo.full_name) }
      else
        memo + repos
      end
    end
  end
end

def has_github_file(full_name, path)
  begin
    client.contents(full_name, path: path)
  rescue Octokit::NotFound
  end
end

def read_github_file(full_name, path)
  begin
    Base64.decode64(client.contents(full_name, path: path).content)
  rescue Octokit::NotFound
    ''
  end
end

def profile?(name)
  PROFILES.include?(name)
end

def template?(name)
  TEMPLATES.include?(name)
end

def specification?(name)
  SPECIFICATIONS.include?(name)
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
    base_url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/main/'

    ids_to_repos = {}
    CSV.parse(URI.open("#{base_url}/extension_versions.csv").read, headers: true).each do |version|
      parts = URI.parse(version.fetch('Base URL'))
      # Assumes different versions of the same extension use the same repository.
      if ['bitbucket.org', 'gitlab.com', 'raw.githubusercontent.com'].include?(parts.hostname)
        ids_to_repos[version.fetch('Id')] = parts.path.split('/')[1..2].join('/')
      else
        raise "#{parts.hostname} not supported (#{version['Id']})"
      end
    end

    repos_to_core = {}
    CSV.parse(URI.open("#{base_url}/extensions.csv").read, headers: true).each do |extension|
      repos_to_core[ids_to_repos.fetch(extension.fetch('Id'))] = extension.fetch('Core') == 'true'
    end

    repos_to_core
  end
end


Dir['tasks/*.rake'].each { |r| import r }
