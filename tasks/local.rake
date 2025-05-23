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
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/main/build/extensions.json'
    JSON.load(URI.open(url).read)['extensions'].each do |extension|
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
  ]

  desc 'Report which non-extension repositories are not cloned'
  task :uncloned do
    basedir = variables('BASEDIR')[0]

    extension_repositories = Set.new
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/main/build/extensions.json'
    JSON.load(URI.open(url).read)['extensions'].each do |extension|
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

    # find . -path '*/.github/workflows/*' ! -path '*/node_modules/*' ! -path '*/vendor/*' ! -name a11y.yml \
    # ! -name automerge.yml ! -name ci.yml ! -name deploy.yml ! -name docker.yml ! -name i18n.yml ! -name js.yml \
    # ! -name lint.yml ! -name pypi.yml ! -name release.yml ! -name shell.yml ! -name spellcheck.yml
    workflows = {
      'ci' => 'CI',
      'lint' => 'Lint',
      'js' => 'Lint JavaScript',
      'shell' => 'Lint Shell',
      'i18n' => 'Translations',
      'a11y' => 'Accessibility',
      'spellcheck' => 'Spell-check',
    }

    ignore_repos = Set.new([
      # The workflows are reused but not run.
      '.github',
    ])

    if ENV['ORG'] != 'open-contracting-partnership'
      output += [
        '',
        'Tech support priority can be assessed based on the impact of the project becoming unavailable and the degree of usage, which can be assessed based on [Python package downloads](http://www.pypi-stats.com/author/?q=30327), [GitHub traffic](https://github.com/open-contracting/standard-development-handbook/issues/76#issuecomment-334540063) and user feedback.',
        '',
        'In addition to the below, within the [OpenDataServices](https://github.com/OpenDataServices) organization, the `flatten-tool`, `sphinxcontrib-jsonschema` and `sphinxcontrib-opendataservices` dependencies are relevant.',
        '',
        "*Stmts* is the number of statements, measured by Coveralls. For example, the assignment of a dict literal or a list comprehension is a single statement, which can be spread across many lines of code (e.g. measured by [Tokei](https://github.com/XAMPPRocky/tokei)). This is more informative, because developers generally reason at the level of statements.",
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
            '|Build|Docs|Stmts|Name|',
            '|-|-|-|-|',
          ]
        end

        matches.sort_by(&:full_name).each do |repo|
          if repo.archived || repo.private || ignore_repos.include?(repo.name)
            next
          end

          line = '|'
          loc = ''

          begin
            hooks = repo.rels[:hooks].get.data
          rescue Octokit::NotFound
            hooks = []
          end

          # Replace with https://docs.github.com/en/rest/reference/actions#list-repository-workflows
          workflow_files = {}
          workflows.each do |basename, label|
            workflow_files[basename] = read_github_file(repo.full_name, ".github/workflows/#{basename}.yml")
            if !workflow_files[basename].empty?
              line << " [![#{label}](https://github.com/#{repo.full_name}/actions/workflows/#{basename}.yml/badge.svg)](https://github.com/#{repo.full_name}/actions/workflows/#{basename}.yml)"
            end
          end

          if !workflow_files['ci'].empty?
            if ['Tools', 'Extension tools', 'Internal tools', 'Documentation dependencies'].include?(heading)
              tox = read_github_file(repo.full_name, 'tox.ini')

              if [workflow_files['ci'], tox].any?{ |contents| contents.include?('coveralls') }
                line << " [![Coverage Status](https://coveralls.io/repos/github/#{repo.full_name}/badge.svg?branch=#{repo.default_branch})](https://coveralls.io/github/#{repo.full_name}?branch=#{repo.default_branch})"

                loc = URI.open("https://coveralls.io/github/#{repo.full_name}").read.match(%r{<strong>(\d+)</strong>\s+relevant lines covered})[1]
              end
            end
          end

          # open-contracting https://github.com/organizations/open-contracting/settings/installations/20658712
          # open-contracting-extensions https://github.com/organizations/open-contracting-extensions/settings/installations/57656794
          if has_github_file(repo.full_name, ".pre-commit-config.yaml")
            line << " [![pre-commit.ci status](https://results.pre-commit.ci/badge/github/#{repo.full_name}/#{repo.default_branch}.svg)](https://results.pre-commit.ci/latest/github/#{repo.full_name}/#{repo.default_branch})"
          end

          line << '|'

          if ENV['ORG'] != 'open-contracting-partnership' && !REPOSITORY_CATEGORIES_WITHOUT_DOCS.include?(heading)
            hook = hooks.find{ |datum| datum.config.url && datum.config.url[%r{\Ahttps://readthedocs.org/api/v2/webhook/([^/]+)}] }
            if hook
              line << "[Docs](https://#{$1}.readthedocs.io/)"
            end
            line << "|#{loc}|"
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
