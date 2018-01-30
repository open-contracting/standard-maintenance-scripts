namespace :release do
  desc 'Reviews open pull requests and recent changes to core extensions'
  task :review_extensions do
    # See http://ocds-standard-development-handbook.readthedocs.io/en/latest/standard/technical/deployment/
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
end
