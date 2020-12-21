# Run all these commands with the `-s` flag.

# Prints the status of all unclean repositories.
status:
	for dir in */; do \
		if [ -d $$dir/.git ]; then \
			cd $$dir; \
			if [[ ! -z `git st` ]]; then \
				echo $$dir; \
				git st; \
			fi; \
			cd ..; \
		fi \
	done

# Checks whether any repositories have unpushed commits.
#
# If you get errors like "fatal: No upstream configured for branch '<branch>'",
# then you must `git push -u origin`.
ahead:
	for dir in */; do \
		if [ -d $$dir/.git ]; then \
			cd $$dir; \
			if [[ ! -z `git remote` ]] && [[ ! -z `git rev-list @{u}..` ]]; then \
				echo $$dir; \
				git rev-list @{u}..; \
			fi; \
			cd ..; \
		fi \
	done

# Prints a repository's branch if it's not master.
branch:
	for dir in */; do \
		if [ -d $$dir/.git ]; then \
			cd $$dir; \
			if [[ `git branch` != "* main" ]] && [[ `git branch` != "* master" ]] && [[ `git branch` != "* gh-pages" ]] && [[ `git branch | xargs` != "gh-pages * master" ]] && [[ `git branch | xargs` != "* gh-pages master" ]]; then \
				echo $$dir; \
				git branch; \
			fi; \
			cd ..; \
		fi \
		done

# Prints a repository's stashes.
stash:
	for dir in */; do \
		if [ -d $$dir/.git ]; then \
			cd $$dir; \
			if [[ ! -z `git stash list` ]]; then \
				echo $$dir; \
				git stash list; \
			fi; \
			cd ..; \
		fi \
		done

# Makes a commit on each repository.
commit:
	for dir in */; do \
		if [ -d $$dir/.git ]; then \
			echo $$dir; \
			cd $$dir; \
			git commit -q ${ARGS}; \
			cd ..; \
		fi \
	done

# Pushes all repositories with unpushed commits.
push:
	for dir in */; do \
		if [ -d $$dir/.git ]; then \
			cd $$dir; \
			if [[ ! -z `git remote` ]] && [[ ! -z `git rev-list @{u}..` ]]; then \
				echo $$dir; \
				git -q push; \
			fi; \
			cd ..; \
		fi \
	done
