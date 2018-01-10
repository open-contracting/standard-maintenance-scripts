namespace :pulls do
  desc 'Lists the pull requests from a given branch'
  task :list do
    ref = variables('REF')[0]

    repos.each do |repo|
      pull = repo.rels[:pulls].get.data.find{ |pull| pull.head.ref == ref }
      if pull
        puts pull.html_url
      end
    end
  end

  desc 'Creates pull requests from a given branch'
  task :create do
    ref, body = variables('REF', 'BODY')

    repos.each do |repo|
      if repo.rels[:pulls].get.data.none?{ |pull| pull.head.ref == ref }
        branch = repo.rels[:branches].get.data.find{ |branch| branch.name == ref }
        if branch
          title = client.commit(repo.full_name, branch.commit.sha).commit.message
          begin
            pull = client.create_pull_request(repo.full_name, repo.default_branch, ref, title, body)
            puts "#{pull.html_url} #{title.bold}"
          rescue Octokit::UnprocessableEntity => e
            if e.errors[0][:message][/\ANo commits between master and \S+\z/]
              client.delete_branch(repo.full_name, ref)
            else
              raise e
            end
          end
        end
      end
    end
  end

  desc 'Replaces the descriptions of pull requests from a given branch'
  task :update do
    ref, body = variables('REF', 'BODY')

    repos.each do |repo|
      pull = repo.rels[:pulls].get.data.find{ |pull| pull.head.ref == ref }
      if pull
        client.update_pull_request(repo.full_name, pull.number, body: body)
        puts pull.html_url
      end
    end
  end

  desc 'Merges pull requests from a given branch'
  task :merge do
    ref = variables('REF')[0]

    repos.each do |repo|
      pull = repo.rels[:pulls].get.data.find{ |pull| pull.head.ref == ref }
      if pull
        begin
          if client.merge_pull_request(repo.full_name, pull.number)
            client.delete_branch(repo.full_name, ref)
          end
          puts pull.html_url
        rescue Octokit::MethodNotAllowed => e
          puts "#{pull.html_url} #{e.to_s.bold}"
        end
      end
    end
  end

  desc 'Compares the given branch to the default branch'
  task :compare do
    ref = variables('REF')[0]

    repos.each do |repo|
      pull = repo.rels[:pulls].get.data.find{ |pull| pull.head.ref == ref }
      if pull
        diff = client.compare(repo.full_name, repo.default_branch, ref, accept: 'application/vnd.github.v3.diff')

        puts "#{pull.html_url} #{pull.rels[:comments].get.data.size.to_s.bold} comments"
        puts "#{pull.html_url}/files"
        puts diff
        puts "press enter to continue"

        $stdin.gets
      end
    end
  end
end
