namespace :pulls do
  desc 'Creates pull requests from a given branch'
  task :create do
    ref, body = variables('REF', 'BODY')

    repos.each do |repo|
      if repo.rels[:pulls].get.data.none?{ |pull| pull.head.ref == ref }
        branch = repo.rels[:branches].get.data.find{ |branch| branch.name == ref }
        if branch
          title = client.commit(repo.full_name, branch.commit.sha).commit.message
          pull = client.create_pull_request(repo.full_name, repo.default_branch, ref, title, body)
          puts "#{pull.html_url} #{title.bold}"
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
        if client.merge_pull_request(repo.full_name, pull.number)
          client.delete_branch(repo.full_name, ref)
        end
        puts pull.html_url
      end
    end
  end
end
