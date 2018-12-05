namespace :registry do
  desc 'Prepare the content of extension_versions.csv'
  task :extension_versions do
    identifiers = {
      'additionalContactPoints' => 'additionalContactPoint',
      'bid' => 'bids',
      'budget_breakdown' => 'budget',
      'budget_projects' => 'budget_project',
      'contract_signatories' => 'signatories',
      'documentation' => 'documentation_details',
      'enquiry' => 'enquiries',
      'multiple_buyers' => 'contract',
      'participationFee' => 'participation_fee',
      'partyDetails_scale' => 'partyScale',
      'riskAllocation' => 'risk_allocation',
      'transactions_relatedMilestone' => 'transaction_milestones',

      # Extensions not in registry (yet).
      'api' => false,
      'exchangeRate' => false,
      'contractRegister' => false,
      'coveredBy' => false,
      'memberOf' => false,
      'options' => false,
      'procurementMethodModalities' => false,
      'recurrence' => false,

      # Profiles not in registry (yet).
      'for-eu' => false,
      'for-gpa' => false,
    }

    new_lines = []
    repos.each do |repo|
      if extension?(repo.name, templates: false)
        data = repo.rels[:releases].get.data
        id = repo.name.gsub(/\Aocds_|_extension\z/, '')
        id = identifiers.fetch(id, id)

        if id != false
          new_lines << [
            id,
            nil,
            repo.default_branch,
            "https://raw.githubusercontent.com/#{repo.full_name}/#{repo.default_branch}/",
            "#{repo.html_url}/archive/#{repo.default_branch}.zip",
          ]

          if data.any?
            data.each do |datum|
              new_lines << [
                id,
                datum.published_at.strftime('%Y-%m-%d'),
                datum.tag_name,
                "https://raw.githubusercontent.com/#{repo.full_name}/#{datum.tag_name}/",
                datum.zipball_url,
              ]
            end
          end
        end
      end
    end

    # Handle any extension versions that aren't within the repositories we track.
    url = 'https://raw.githubusercontent.com/open-contracting/extension_registry/master/extension_versions.csv'
    old_lines = CSV.parse(open(url).read, headers: true).entries.map(&:fields)
    lines = new_lines + (old_lines - new_lines)

    puts CSV.generate_line(['Id', 'Date', 'Version', 'Base URL', 'Download URL'])
    puts lines.map{ |line| CSV.generate_line(line) }.sort
  end
end
