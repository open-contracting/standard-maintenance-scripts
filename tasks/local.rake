def each_path
  basedir = variables('BASEDIR')[0]

  updated = []

  paths = Dir[basedir] + Dir[File.join(basedir, '*')]

  paths.each do |path|
    yield path, updated
  end

  if updated.any?
    puts "updated: #{updated.join(' ')}"
  end
end

namespace :local do
  desc 'Regenerates the badges pages'
  task :badges do
    def tech_support_priority(repo)
      if extension?(repo.name, profiles: false, templates: false)
        if core_extensions[repo.full_name]
          '✴️✴️'
        else
          '✴️'
        end
      elsif profile?(repo.name)
        '✴️✴️'
      elsif DOCUMENTATION_DEPENDENCIES.include?(repo.name)
        '✴️✴️'
      elsif LEGACY.include?(repo.name)
        'N/A'
      else
        TECH_SUPPORT_PRIORITIES.fetch(repo.name)
      end
    end

    if ENV['ORG']
      filename = "badges-#{ENV['ORG']}.md"
    else
      filename = 'badges.md'
    end

    output = [
      '# Project Statuses',
    ]

    if ENV['ORG'] != 'open-contracting-partnership'
      output += [
        '',
        'Tech support priority is assessed based on the impact of the project becoming unavailable and the degree of usage, which can be assessed based on [Python package downloads](http://www.pypi-stats.com/author/?q=30327), [GitHub traffic](https://github.com/open-contracting/standard-development-handbook/issues/76#issuecomment-334540063) and user feedback.',
        '',
        'In addition to the below, within the [OpenDataServices](https://github.com/OpenDataServices) organization, `cove` is critical (as a step in implementation), and `sphinxcontrib-jsonschema` and `sphinxcontrib-opendataservices` are high (as dependencies of `standard`).'
      ]
    end

    REPOSITORY_CATEGORIES.each do |heading, condition|
      matches = repos.select(&condition)

      if matches.any?
        output += [
          '',
          "## #{heading}",
          '',
        ]

        if ENV['ORG'] == 'open-contracting-partnership'
          output += [
            '|Build|Name|',
            '|-|-|',
          ]
        elsif REPOSITORY_CATEGORIES_WITHOUT_DOCS.include?(heading)
          output += [
            '|Priority|Build|Name|',
            '|-|-|-|',
          ]
        else
          output += [
            '|Priority|Build|Docs|Name|',
            '|-|-|-|-|',
          ]
        end

        matches.each do |repo|
          line = '|'

          begin
            hooks = repo.rels[:hooks].get.data
          rescue Octokit::NotFound
            hooks = []
          end

          if ENV['ORG'] != 'open-contracting-partnership'
            priority = tech_support_priority(repo)

            line << "#{priority}|"
          end

          # Support both GitHub Services and GitHub Apps until GitHub Services fully retired.
          hook = hooks.find{ |datum| datum.name == 'travis' || datum.config.url == 'https://notify.travis-ci.org' }
          if hook
            line << "[![Build Status](https://travis-ci.org/#{repo.full_name}.svg)](https://travis-ci.org/#{repo.full_name})"
            if ['Tools', 'Extension tools', 'Internal tools', 'Documentation dependencies'].include?(heading)
              contents = read_github_file(repo.full_name, '.travis.yml')
              if contents.include?('coveralls')
                line << " [![Coverage Status](https://coveralls.io/repos/github/#{repo.full_name}/badge.svg?branch=master)](https://coveralls.io/github/#{repo.full_name}?branch=master)"
              end
              contents = read_github_file(repo.full_name, 'tox.ini')
              if contents.include?('coveralls')
                line << " [![Coverage Status](https://coveralls.io/repos/github/#{repo.full_name}/badge.svg?branch=master)](https://coveralls.io/github/#{repo.full_name}?branch=master)"
              end
            end
            line << '|'
          else
            line << '-|'
          end

          if ENV['ORG'] != 'open-contracting-partnership' && !REPOSITORY_CATEGORIES_WITHOUT_DOCS.include?(heading)
            hook = hooks.find{ |datum| datum.config.url && datum.config.url[%r{\Ahttps://readthedocs.org/api/v2/webhook/([^/]+)}] }
            if hook
              line << "[Docs](https://#{$1}.readthedocs.io/)"
              line << '|'
            else
              line << '-|'
            end
          end

          output << line + "[#{repo.name}](#{repo.html_url})|"

          print '.'
        end
      end
    end

    output << ''

    File.open(filename, 'w') do |f|
      f.write(output.join("\n"))
    end
  end

  desc 'Adds template content to extension readmes'
  task :readmes do
    template = <<-END

## Issues

Report issues for this extension in the [ocds-extensions repository](https://github.com/open-contracting/ocds-extensions/issues), putting the extension's name in the issue's title.
    END

    each_path do |path, updated|
      repo_name = File.basename(path)

      if Dir.exist?(path) && extension?(repo_name)
        readme_path = File.join(path, 'README.md')
        content = File.read(readme_path)

        if !content[template]
          if !content.end_with?("\n")
            content << "\n"
          end

          content << template
          updated << repo_name

          File.open(readme_path, 'w') do |f|
            f.write(content)
          end
        end
      end
    end
  end

  desc 'Update extension.json'
  task :extension_json do
    schema = JSON.load(File.read(File.join(File.expand_path(File.dirname(__FILE__)), '..', 'schema', 'extension-schema.json')))

    extension_ids = {}
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/build/extensions.json'
    JSON.load(open(url).read)['extensions'].each do |extension|
      full_name = extension['url'][%r{\Ahttps://raw\.githubusercontent\.com/([^/]+/[^/]+)}, 1]
      if full_name['open-contracting-extensions']
        extension_ids[full_name.sub('open-contracting-extensions', 'open-contracting')] = extension['id']
      end
      extension_ids[full_name] = extension['id']
    end

    each_path do |path, updated|
      repo_name = File.basename(path)

      if Dir.exist?(path) && extension?(repo_name)
        full_name = File.read(File.join(path, '.git', 'config')).match(/git@github.com:(\S+)\.git/)[1]
        file_path = File.join(path, 'extension.json')
        original = JSON.load(File.read(file_path))
        expected = Marshal.load(Marshal.dump(original))

        content = {}

        # All extensions are presently only compatible with 1.1.
        original['compatibility'] = ['1.1']

        # Standardize the order of fields.
        schema['properties'].each_key do |key|
          if original.key?(key)
            content[key] = original[key]
          end
        end

        # Convert from old to new format.
        %w(name description).each do |field|
          if String === content[field]
            content[field] = { 'en' => content[field] }
          end
        end

        if String === content['compatibility']
          content['compatibility'] = case content['compatibility']
          when /\A>=1\.1/
            ['1.1']
          when /\A>=1\.0/
            ['1.0', '1.1']
          else
            raise "unexpected compatibility '#{content['compatibility']}'"
          end
        end

        if content.key?('dependencies') && content['dependencies'].empty?
          content.delete('dependencies')
        end

        if extension_ids.include?(full_name)
          content['documentationUrl'] = { 'en' => "https://extensions.open-contracting.org/en/extensions/#{extension_ids[full_name]}/" }
        else
          content['documentationUrl'] = { 'en' => "https://github.com/#{full_name}" }
          puts "extension not in registry: #{full_name}"
        end

        codelists = Set.new(Dir[File.join(path, 'codelists', '*')].map{ |path| File.basename(path) })
        if String === content['codelists'] || codelists != Set.new(content['codelists'])
          content['codelists'] = codelists.to_a.sort
        end

        schemas = Set.new(Dir[File.join(path, '*-schema.json')].map{ |path| File.basename(path) })
        if String === content['schemas'] || schemas != Set.new(content['schemas'])
          content['schemas'] = schemas.to_a.sort
        end

        # Write the content, if changed.
        if JSON.dump(content) != JSON.dump(expected)
          updated << repo_name
          File.open(file_path, 'w') do |f|
            f.write(JSON.pretty_generate(content) + "\n")
          end
        end
      end
    end
  end
end
