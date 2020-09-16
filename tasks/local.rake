namespace :local do
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

  def get_extension_ids
    extension_ids = {}
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/build/extensions.json'
    JSON.load(open(url).read)['extensions'].each do |extension|
      full_name = extension['url'][%r{\Ahttps://raw\.githubusercontent\.com/([^/]+/[^/]+)}, 1]
      extension_ids[full_name] = extension['id']
    end
    extension_ids
  end

  REPOSITORY_CATEGORIES_WITHOUT_DOCS = [
    'Specifications',
    'Guides',
    'Templates',
    'Profiles',
    'Extensions',
    'Legacy',
  ]

  CODECLIMATE_IDS = {
    'cove-oc4ids' => 'f14b93f3eb3d0548d558',
    'cove-ocds' => 'c0f756a34d5cde6f3c2a',
    'extension-explorer' => '271bbb582eabae79bf84',
    'extension_registry' => '3e4987f75d1a5d3b7414',
    'extension_registry.py' => 'bce37ba7b2754e072793',
    'jscc' => '0c8c3401e5030701fb3e',
    'kingfisher-archive' => '1136c0a79cb06df1540a',
    'kingfisher-colab' => '654ae197655319a3516d',
    'kingfisher-collect' => 'd99c7be71834abe83a81',
    'kingfisher-process' => '28efa551a6da047e08f1',
    'kingfisher-views' => 'bb8dcc8a751e3d683407',
    'lib-cove-oc4ids' => 'd217b495e80fd4e392ac',
    'lib-cove-ocds' => 'd4c6b5a47d84473f8a1d',
    'ocds-babel' => 'f29410cef5b0f9a16314',
    'ocds-merge' => '1acee37f89fb00d7e086',
    'ocdskit' => 'd4cb38a9007ee5de2b37',
    'sphinxcontrib-opencontracting' => '5766e1bac00a61263a90',
    'standard-maintenance-scripts' => '76db8a8485fc75e3c8a0',
    'standard-search' => '9ae38bf02160da764f56',
    'toucan' => 'd6c699bd328cac875ffa',
  }

  desc 'Report which non-extension repositories are not cloned'
  task :uncloned do
    basedir = variables('BASEDIR')[0]

    extension_repositories = Set.new
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/build/extensions.json'
    JSON.load(open(url).read)['extensions'].each do |extension|
      extension_repositories << URI.parse(extension['url']).path.split('/')[2]
    end

    cloned_repositories = Set.new(Dir[File.join(basedir, '*')].map{ |path| File.basename(path) })

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

  desc 'Update extension.json'
  task :extension_json do
    extension_ids = get_extension_ids

    each_path do |path, updated|
      repo_name = File.basename(path)

      if Dir.exist?(path) && extension?(repo_name) && !profile?(repo_name)
        full_name = File.read(File.join(path, '.git', 'config')).match(/git@github.com:(\S+)\.git/)[1]
        file_path = File.join(path, 'extension.json')

        content = JSON.load(File.read(file_path))
        expected = Marshal.load(Marshal.dump(content))

        # Make changes to `content`
        if extension_ids.include?(full_name)
          content['documentationUrl'] = { 'en' => "https://extensions.open-contracting.org/en/extensions/#{extension_ids[full_name]}/" }
        else
          content['documentationUrl'] = { 'en' => "https://github.com/#{full_name}" }
        end

        content['contactPoint'] = { 'name' => 'Open Contracting Partnership', 'email' => 'data@open-contracting.org' }

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

  desc 'Convert code titles to sentence case'
  task :code_titles do
    extension_ids = get_extension_ids

    each_path do |path, updated|
      repo_name = File.basename(path)
      codelists_directory = File.join(path, 'codelists')

      if Dir.exist?(path) && extension?(repo_name) && !profile?(repo_name) && Dir.exists?(codelists_directory)
        Dir[File.join(codelists_directory, '*.csv')].each do |filename|
          expected = File.read(filename)
          table = CSV.parse(expected, headers: true)

          if table.headers.include?('Title')
            table.each do |row|
              row['Title'] = row['Title'].capitalize
            end
          end

          if table.to_s != expected
            File.write(filename, table)
          end
        end
      end
    end
  end

  desc 'Regenerates the badges pages'
  task :badges do
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
        'Tech support priority can be assessed based on the impact of the project becoming unavailable and the degree of usage, which can be assessed based on [Python package downloads](http://www.pypi-stats.com/author/?q=30327), [GitHub traffic](https://github.com/open-contracting/standard-development-handbook/issues/76#issuecomment-334540063) and user feedback.',
        '',
        'In addition to the below, within the [OpenDataServices](https://github.com/OpenDataServices) organization, the `lib-cove`, `lib-cove-web`, `sphinxcontrib-jsonschema` and `sphinxcontrib-opendataservices` dependencies are relevant.'
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
            '|Build|Name|',
            '|-|-|',
          ]
        else
          output += [
            '|Build|Docs|Name|',
            '|-|-|-|',
          ]
        end

        matches.each do |repo|
          if repo.archived
            next
          end

          line = '|'

          begin
            hooks = repo.rels[:hooks].get.data
          rescue Octokit::NotFound
            hooks = []
          end

          # Support both GitHub Services and GitHub Apps until GitHub Services fully retired.
          test_hook = hooks.find{ |datum| datum.name == 'travis' || datum.config.url == 'https://notify.travis-ci.org' }

          maintainability_hook = hooks.find{ |datum| datum.config.url == 'https://codeclimate.com/webhooks' }

          ci = read_github_file(repo.full_name, '.github/workflows/ci.yml')
          lint = read_github_file(repo.full_name, '.github/workflows/lint.yml')

          # https://github.com/octokit/octokit.rb/issues/1216
          if !ci.empty?
            line << "[![Build Status](https://github.com/#{repo.full_name}/workflows/CI/badge.svg)](https://github.com/#{repo.full_name}/actions?query=workflow%3ACI)"
            if test_hook
              puts client.remove_hook(repo.full_name, test_hook.id)
            end
          elsif !lint.empty?
            line << "[![Build Status](https://github.com/#{repo.full_name}/workflows/Lint/badge.svg)](https://github.com/#{repo.full_name}/actions?query=workflow%3ALint)"
            if test_hook
              puts client.remove_hook(repo.full_name, test_hook.id)
            end
          elsif test_hook
            line << "[![Build Status](https://travis-ci.org/#{repo.full_name}.svg)](https://travis-ci.org/#{repo.full_name})"
          end

          if !ci.empty? || !lint.empty? || test_hook
            if ['Tools', 'Extension tools', 'Internal tools', 'Documentation dependencies'].include?(heading)
              tox = read_github_file(repo.full_name, 'tox.ini')
              travis = read_github_file(repo.full_name, '.travis.yml')

              if [ci, lint, tox, travis].any?{ |contents| contents.include?('coveralls') }
                line << " [![Coverage Status](https://coveralls.io/repos/github/#{repo.full_name}/badge.svg?branch=master)](https://coveralls.io/github/#{repo.full_name}?branch=master)"
              end
            end
          end

          if maintainability_hook
            line << " [![Maintainability](https://api.codeclimate.com/v1/badges/#{CODECLIMATE_IDS.fetch(repo.name)}/maintainability)](https://codeclimate.com/github/#{repo.full_name}/maintainability)"
          end

          if !ci.empty? || !lint.empty? || test_hook || maintainability_hook
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
end
