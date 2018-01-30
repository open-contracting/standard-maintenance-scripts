# See http://ocds-standard-development-handbook.readthedocs.io/en/latest/standard/technical/deployment/
namespace :release do
  desc 'Reviews open pull requests and recent changes to core extensions'
  task :review_extensions do
    repos.each do |repo|
      if core_extensions[repo.name]
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
    name = "Fixed version for OCDS #{ref[1..-1]}"

    repos.each do |repo|
      if core_extensions[repo.name]
        content = Base64.decode64(client.readme(repo.full_name).content)
        match = content.match(/^### #{ref}\n\n([^#]+)/)
        if match
          begin
            release = client.create_release(repo.full_name, ref, {name: name, body: match[1]})
            puts release.html_url
          rescue Octokit::UnprocessableEntity => e
            if e.errors[0][:code] == 'already_exists'
              puts "#{repo.html_url}/releases/tag/#{ref} #{'already exists'.bold}"
            else
              raise e
            end
          end
        else
          puts "#{repo.html_url} Couldn't find changelong in README.md"
        end
      end
    end
  end
end
