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
    output = [
      '# Project Build and Dependency Status',
    ]

    repos.partition{ |repo| !extension?(repo.name) }.each_with_index do |set, index|
      output << ''

      if index.zero?
        output << "## Repositories"
      else
        output << "## Extensions"
      end

      output += [
        '',
        'Name|Build|Dependencies',
        '-|-|-',
      ]

      set.each do |repo|
        hooks = repo.rels[:hooks].get.data

        line = "[#{repo.name}](#{repo.html_url})|"

        hook = hooks.find{ |datum| datum.name == 'travis' }
        if hook && hook.active
          line << "[![Build Status](https://travis-ci.org/#{repo.full_name}.svg)](https://travis-ci.org/#{repo.full_name})"
        else
          line << '-'
        end

        line << '|'

        hook = hooks.find{ |datum| datum.config.url == 'https://requires.io/github/web-hook/' }
        if hook && hook.active
          line << "[![Requirements Status](https://requires.io/github/#{repo.full_name}/requirements.svg)](https://requires.io/github/#{repo.full_name}/requirements/)"
        else
          line << '-'
        end

        output << line

        print '.'
      end
    end

    output << ''

    File.open('badges.md', 'w') do |f|
      f.write(output.join("\n"))
    end
  end

  desc 'Sets the enum in a JSON Schema to match the codes in the CSV files of closed codelists'
  task :codelists do
    def collect_codelists(path)
      Dir[File.join(path, '**', '*.csv')].each do |filename|
        unless Pathname.new(filename).each_filename.to_a.include?('codelists_translated')
          basename = File.basename(filename)
          if CODELISTS[basename] && CODELISTS[basename] != CSV.read(filename, headers: true)
            raise "conflicting codelists #{basename}"
          end
          CODELISTS[basename] = CSV.read(filename, headers: true)
        end
      end
    end

    # This method matches `validate_codelist_enum` in `test_json.py`.
    def update_codelist_enum(data)
      case data
      when Hash
        if data['codelist']
          if String === data.fetch('type')
            types = [data['type']]
          else
            types = data['type']
          end

          if !data.fetch('openCodelist')
            codes = CODELISTS.fetch(data['codelist']).map{ |row| row.fetch('Code') }

            if types.include?('string')
              if types.include?('null')
                codes << nil
              end
              data['enum'] = codes
            elsif types.include?('array')
              data['items']['enum'] = codes
            end
          end
        else
          data.each do |key,value|
            data[key] = update_codelist_enum(value)
          end
        end
      when Array
        data.map! do |item|
          update_codelist_enum(item)
        end
      end

      data
    end

    CODELISTS = {}

    standard = variables('STANDARD')[0]

    collect_codelists(standard)

    each_path do |path, updated|
      repo_name = File.basename(path)

      if Dir.exist?(path) && extension?(repo_name)
        collect_codelists(path)

        Dir[File.join(path, '**', '*.json')].each do |filename|
          content = JSON.load(File.read(filename))
          expected = Marshal.load(Marshal.dump(content))

          # If the JSON file is a JSON Schema file.
          if content['$schema'] || content['definitions'] || content['properties']
            update_codelist_enum(content)

            if expected != content
              updated << repo_name
              File.open(filename, 'w') do |f|
                f.write(JSON.pretty_generate(content) + "\n")
              end
            end
          end
        end
      end
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

  desc 'Update extension.json to its new format'
  task :extension_json do
    each_path do |path, updated|
      repo_name = File.basename(path)

      if Dir.exist?(path) && extension?(repo_name)
        file_path = File.join(path, 'extension.json')
        content = JSON.load(File.read(file_path))
        expected = Marshal.load(Marshal.dump(content))

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

        if !content.key?('documentationUrl')
          content['documentationUrl'] = { 'en' => "https://github.com/open-contracting/#{repo_name}" }
        end

        codelists = Set.new(Dir[File.join(path, 'codelists', '*')].map{ |path| File.basename(path) })

        if String === content['codelists'] || codelists != Set.new(content['codelists'])
          content['codelists'] = codelists.to_a.sort
        end

        if expected != content
          updated << repo_name
          File.open(file_path, 'w') do |f|
            f.write(JSON.pretty_generate(content) + "\n")
          end
        end
      end
    end
  end
end
