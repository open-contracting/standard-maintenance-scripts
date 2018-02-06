namespace :resources do
  class ResourceURL
    attr_reader :url, :location

    def initialize(url, location)
      @url = url
      @location = location
    end

    def google_id
      @google_id ||= dereferenced_url['google.com'] && dereferenced_url[%r{/([^/]{25,})/}, 1]
    end

    def type
      case dereferenced_url
      when %r{\Ahttps://docs\.google\.com/(?:document|spreadsheets)/d/[^/]+/\z}
        'bare'
      when %r{\Ahttps://docs\.google\.com/(?:document|presentation)/d/[^/]+/edit\z},
           %r{\Ahttps://docs\.google\.com/spreadsheets/d/[^/]+/edit#gid=\d+\z},
           %r{\Ahttps://docs.google.com/document/d/[^/]+/edit(?:\?usp=sharing|#heading=h\.[a-z0-9]+)\z}
        'edit'
      when %r{\Ahttps://docs\.google\.com/spreadsheets/d/[^/]+/copy\z}
        'copy'
      when %r{\Ahttps://drive\.google\.com/drive/folders/[^/?]+\z}
        'folder'
      when %r{\Ahttps://drive\.google\.com/file/d/[^/]+/view\z}
        'view'
      when %r{\Ahttps://drive\.google\.com/open\?id=[^&]+\z}
        'open'
      else
        raise dereferenced_url
      end
    end

    def dereferenced_url
      @dereferenced_url ||= begin
        if url['bit.ly']
          Faraday.get(url).headers['location']
        else
          url
        end
      end
    end
  end

  def get_resources
    data = open('https://www.open-contracting.org/resources/').read
    JSON.load(data[/resources: (.+),\n/, 1])
  end

  def get_resource_urls(resource)
    urls = []

    if resource['fields']['attachments'] === false
      urls << ResourceURL.new(resource['fields']['link'], 'link')
    else
      resource['fields']['attachments'].each_with_index do |attachment, i|
        urls << ResourceURL.new(attachment['file'], "attachment #{i}")
      end
    end

    resource['content'].scan(/http.+?(?="|\.<)/).each do |url|
      urls << ResourceURL.new(url, 'content')
    end

    urls
  end

  def is_google_url(url)
    url[/(?:docs|drive)\.google\.com/]
  end

  def taxonomy_values(resource, key)
    if resource['taxonomies'][key].any?
      resource['taxonomies'][key].values
    else
      []
    end
  end

  def resource_language(resource)
    matcher = resource['title'].match(/\(([A-Z]{2})\)\z/)
    if matcher
      matcher[1]
    else
      'EN'
    end
  end

  def resource_error(resource, message='')
    puts "https://www.open-contracting.org/wp-admin/post.php?post=#{resource['id']}&action=edit: #{message}"
  end

  desc 'Prints all links from the Resources section of the OCP website'
  task :links do
    groups = {}

    get_resources.each do |resource|
      get_resource_urls(resource).each do |resource_url|
        groups[resource_url.location] ||= Set.new
        groups[resource_url.location] << resource_url.url
      end
    end

    groups.each do |location, urls|
      puts "\n#{location}"
      puts urls.to_a.sort
    end
  end

  desc 'Prints the bit.ly links from the Resources section of the OCP website as tab-separated values'
  task :bitly do
    # Bit.ly links are catalogued in https://docs.google.com/spreadsheets/d/1gTcRIzQOdF_jbxDfauZP-f-cfiAUSQy6SQm0-jAKBho/edit#gid=0

    rows = []

    puts CSV.generate_line([
      'Name',
      'Language',
      'Link',
      'Link type',
      'Bit.ly link',
      'Resource link',
    ], col_sep: "\t")

    get_resources.each do |resource|
      get_resource_urls(resource).each do |resource_url|
        if resource_url.url['bit.ly']
          rows << [
            HTMLEntities.new.decode(resource['title']),
            resource_language(resource),
            resource_url.dereferenced_url,
            resource_url.type,
            resource_url.url,
            "https://www.open-contracting.org/wp-admin/post.php?post=#{resource['id']}&action=edit",
          ]
        end
      end
    end

    rows.sort_by{ |row| row[4] }.each do |row|
      puts CSV.generate_line(row, col_sep: "\t")
    end
  end

  desc 'Lints the Resources section of the OCP website'
  task :check do
    resources = get_resources
    resources_urls = {}
    resource_urls = {}
    google_urls = {}

    bitly_exceptions = Set.new([
      1332, # Use Cases and Requirements for Extractive Industries and Land Extensions
      1565, # Open Contracting Partnership Learning Plan
      2433, # Red flags for integrity: Giving the green light to open data solutions
      2734, # Working paper: aid and contracting data
      2749, # Methodology for Open Contracting Scoping Studies
      2914, # Open Contracting Scope Study Cote d’Ivoire
    ])

    resources.each do |resource|
      # Cache the resource URLs.
      resources_urls[resource['id']] = get_resource_urls(resource)

      # Collect the unique resource for each URL not occuring in the content of a resource.
      # Warn if the URL is used in the links or attachments of multiple resources.
      resources_urls[resource['id']].each do |resource_url|
        url = resource_url.dereferenced_url
        location = resource_url.location
        google_id = resource_url.google_id

        # Content can link to other resources.
        unless location == 'content'
          if resource_urls.key?(url)
            resource_error(resource, "unexpected collision on #{url} (seen at #{resource_urls[url]})")
          else
            resource_urls[url] = resource['link']
          end

          if google_id
            if google_urls.key?(google_id)
              resource_error(resource, "unexpected collision on #{url} (seen at #{google_urls[google_id][0]} as #{google_urls[google_id][1]})")
            else
              google_urls[google_id] = [resource['link'], url]
            end
          end
        end
      end
    end

    # Validate the resources
    resources.each do |resource|
      errors = []
      seen_urls = {}

      # Just check the taxonomies of OCDS resources.
      if resource['title']['OCDS']
        resource_type = taxonomy_values(resource, 'resource-type')[0]
        region = taxonomy_values(resource, 'region')
        open_contracting = taxonomy_values(resource, 'open-contracting')

        if !resource_type
          errors << 'expected Resource Type to not be nil'
        end

        if resource_language(resource) == 'ES'
          expected_region = 'Latin America and the Caribbean'
        else
          expected_region = 'International'
        end
        if !region.include?(expected_region)
          errors << "expected Region to include '#{expected_region}'"
        end

        if resource_type == 'Data tool'
          expected_open_contracting = ['Data standard', 'Implementation']
        else
          expected_open_contracting = ['Data standard']
        end
        if open_contracting != expected_open_contracting
          errors << "expected Open Contracting to be #{expected_open_contracting}"
        end
      end

      resources_urls[resource['id']].each do |resource_url|
        url = resource_url.dereferenced_url
        location = resource_url.location
        original_url = resource_url.url

        match = is_google_url(original_url)
        if match
          # Use bit.ly links to track access to Google Drive files and folders.
          if !bitly_exceptions.include?(resource['id'])
            errors << "use a bit.ly link in #{location} instead of #{original_url}"
          end

          # We only check original URLs because Bit.ly doesn't allow changing URL destinations.
          if !url[%r{\A(?:https://docs\.google\.com/document/d/[^/]+/edit|https://docs\.google\.com/spreadsheets/d/[^/]+/copy|https://docs\.google\.com/spreadsheets/d/[^/]+/edit#gid=\d+|https://drive\.google\.com/drive/folders/[^/?]+|https://drive\.google\.com/file/d/[^/]+/view|https://drive\.google\.com/open\?id=[^&]+)\z}]
            errors << "expected #{location} to match URL pattern (#{url}) (remove '?ts=…', '?usp=sharing', '#heading=…', '/u/0', '/a/open-contracting.org', etc.)"
          end
        end

        # Expect URLs to respond with status code HTTP 200 OK.
        begin
          status = Faraday.get(url).status
          if %w(bare copy open).include?(resource_url.type)
            expected = 302
          else
            expected = 200
          end
          if status != expected
            errors << "expected #{expected}, got #{status} for status code of #{url} in #{location}"
          end
        rescue URI::InvalidURIError, Faraday::ConnectionFailed, ArgumentError => e
          puts "#{e} on GET #{url} for #{resource['link']}"
        end

        # Within each resource, use each URL only once, to avoid having to update URLs in multiple locations.
        if seen_urls.key?(url)
          errors << "remove #{url} from #{location}? (already in #{seen_urls[url]})"
        else
          seen_urls[url] = location
        end

        # Link to resource pages where possible, to avoid having to update URLs in multiple resources.
        if resource_urls.include?(url) && resource_urls[url] != resource['link']
          errors << "replace #{url} in #{location} with #{resource_urls[url]}"
        end
        google_id = resource_url.google_id
        if google_urls.key?(google_id) && google_urls[google_id][0] != resource['link']
          errors << "replace #{url} in #{location} with #{google_urls[google_id][0]}"
        end

        case location
        when 'content'
          # At this time, OCP links in "content" match one of three patterns.
          if url[/www\.open-contracting\.org/] && !url[%r{\Ahttps://www\.open-contracting\.org/(?:\d{4}/\d{2}/\d{2}/[^/]+/|resources/[^/]+/|wp-content/uploads/\d{4}/\d{2}/[^/]+)\z}]
            errors << "expected #{location} to match URL pattern (#{url})"
          end
        when 'link'
          # At this time, OCP links don't occur in "link".
          match = url[/www\.open-contracting\.org/]
          if match
            errors << "expected #{location} to not match '#{match}' (#{url})"
          end
        else # 'attachment #'
          # At this time, all attachments are WordPress uploads.
          if !url[%r{\Ahttps://www\.open-contracting\.org/wp-content/uploads/\d{4}/\d{2}/[^/]+\z}]
            errors << "expected #{location} to match URL pattern (#{url})"
          end
        end
      end

      if errors.any?
        resource_error(resource, HTMLEntities.new.decode(resource['title']))
        errors.each do |error|
          puts "  #{error}"
        end
        puts
      end
    end

    puts "Click Performance > Purge Modules > Page Cache: All after correcting above issues."
  end
end
