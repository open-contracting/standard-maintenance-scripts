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

          # https://github.com/octokit/octokit.rb/issues/1216
          if repo.owner.login == 'open-contracting-extensions'
            line << "![Build Status](https://github.com/#{repo.full_name}/workflows/CI/badge.svg)"
            if hook
              puts client.remove_hook(repo.full_name, hook.id)
            end
          elsif hook
            line << "[![Build Status](https://travis-ci.org/#{repo.full_name}.svg)](https://travis-ci.org/#{repo.full_name})"
          end

          if repo.owner.login == 'open-contracting-extensions' || hook
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
end
