#!/bin/sh

set -x
git branch
git log -1

commit_message="chore(budcustomer): bump nix hash"
commit_author="auto walle"
commit_email="auto@sinanmohd.com"

repo_root="$(git rev-parse --show-toplevel)"
nix_hash_path="$repo_root/services/budCustomer/nix.hash"
npm_lock_path="$repo_root/services/budCustomer/package-lock.json"

early_escape_possible() {
	last_npm_time="$(git log -1 --format="%at" "$npm_lock_path")"
	last_bump_time="$(git log -1 --format="%at" "$nix_hash_path")"

	if [ -z "$last_bump_time" ] || [ -z "$last_npm_time" ] || [ "$last_bump_time" -lt "$last_npm_time" ]; then
		return 1
	else
		return 0
	fi
}

##########
## MAIN ##
##########

if [ ! -e "$nix_hash_path" ] || [ ! -e "$npm_lock_path" ]; then
	echo "expected paths does not exists, are you sure you're running this inside git repo"
	exit 1
fi

if ! git diff-index --quiet --cached HEAD; then
	echo "commit staged changes first"
	exit 1
fi

if early_escape_possible; then
	echo "early escape success, nix bump commit is newer"
	exit 0
else
	echo "npm bump commit is newer, updating hash"
fi

cur_hash="$(cat "$nix_hash_path")"
new_hash="$(prefetch-npm-deps "$npm_lock_path")"
if [ "$cur_hash" != "$new_hash" ]; then
	echo "hash changed: ${cur_hash} -> ${new_hash}"
	echo "$new_hash" >"$nix_hash_path"

	git add "$nix_hash_path"
	git commit --author="$commit_author <$commit_email>" -m "$commit_message"
	git push
else
	echo "hash did not change: waiting for your next commit"
fi
