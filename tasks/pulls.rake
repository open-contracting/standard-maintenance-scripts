namespace :pulls do
  desc 'Creates pull requests from a given branch'
  task :create do
    ref = ENV['REF']
    if ref.nil?
      abort 'usage: rake pulls:create REF=branch'
    end

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

  desc 'Merges pull requests for a given branch'
  task :merge do
    ref = ENV['REF']
    if ref.nil?
      abort 'usage: rake pulls:merge REF=branchtomerge'
    end

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
