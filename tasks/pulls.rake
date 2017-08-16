namespace :pulls do
  def variables(*keys)
    keys.map do |key|
      value = ENV[key]
      if value.nil? || value.empty?
        abort "usage: rake #{ARGV[0]} #{keys.map{ |key| "#{key}=value" }.join(' ')}"
      end
      value
    end
  end

  desc 'Creates pull requests from a given branch'
  task :create do
    ref = variables('REF')[0]

    repos.each do |repo|
      if repo.rels[:pulls].get.data.none?{ |pull| pull.head.ref == ref }
        branch = repo.rels[:branches].get.data.find{ |branch| branch.name == ref }
        if branch
          title = client.commit(repo.full_name, branch.commit.sha).commit.message
          pull = client.create_pull_request(repo.full_name, repo.default_branch, ref, title)
          puts "#{pull.html_url} #{title.bold}"
        end
      end
    end
  end

  desc 'Updates pull request descriptions'
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

  desc 'Merges pull requests for a given branch'
  task :merge do
    ref = variables('REF')[0]

    repos.each do |repo|
      repo.rels[:pulls].get.data.each do |pull|
        if pull.head.ref == ref
          client.merge_pull_request(repo.full_name, pull.number)
          puts pull.html_url
        end
      end
    end
  end
end
