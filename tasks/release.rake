# See http://ocds-standard-development-handbook.readthedocs.io/en/latest/standard/technical/deployment/
namespace :release do
  desc 'Reviews open pull requests and recent changes to core extensions'
  task :review_extensions do
    repos.each do |repo|
      if extension?(repo.name, profiles: false, templates: false) && !core_extensions.key?(repo.full_name)
        puts "extension not in registry: #{repo.full_name}"
      elsif core_extensions[repo.full_name]
        pull_requests = repo.rels[:pulls].get.data
        latest_release = repo.rels[:releases].get.data[0]
        compare = client.compare(repo.full_name, latest_release.tag_name, repo.default_branch)

        if pull_requests.any?
          pull_requests.each do |pull_request|
            puts "#{pull_request.html_url} #{pull_request.title}"
          end
        end

        if compare.status == 'ahead'
          puts "#{compare.html_url} #{compare.ahead_by} commits to #{repo.default_branch} since #{latest_release.tag_name}"
        end
      end
    end
  end

  desc 'Releases new versions of core extensions'
  task :release_extensions do
    ref = variables('REF')[0]

    repos.each do |repo|
      if extension?(repo.name, profiles: false, templates: false) && !core_extensions.key?(repo.full_name)
        puts "extension not in registry: #{repo.full_name}"
      elsif core_extensions[repo.full_name]
        content = Base64.decode64(client.readme(repo.full_name).content)
        match = content.match(/^### #{ref}\n\n([^#]+)/)
        if match
          begin
            release = client.create_release(repo.full_name, ref, {body: match[1]})
            puts release.html_url
          rescue Octokit::UnprocessableEntity => e
            if e.errors[0][:code] == 'already_exists'
              puts "#{repo.html_url}/releases/tag/#{ref} #{'already exists'.bold}"
            else
              raise e
            end
          end
        else
          puts "#{repo.html_url} Couldn't find changelog in README.md"
        end
      end
    end
  end

  desc 'Removes specific releases of repositories'
  task :undo_release_extensions do
    ref = variables('REF')[0]

    repos.each do |repo|
      release = client.releases(repo.full_name).find{ |release| release.tag_name == ref }
      if release
        success = client.delete_release(release.url)
        if success
          puts "#{repo.html_url} deleted #{ref} release: still need to delete local and remote tags: git tag -d #{ref}; git push origin :#{ref}"
        end
      end
    end
  end
end
