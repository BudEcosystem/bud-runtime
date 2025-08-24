#!/bin/sh

fake_hash="sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

commit_message="chore(budcustomer): bump nix hash"
commit_author="auto walle"
commit_email="auto@sinanmohd.com"

repo_root="$(git rev-parse --show-toplevel)"
nix_hash_path="$repo_root/services/budCustomer/nix.hash"
npm_lock_path="$repo_root/services/budCustomer/pnpm-lock.yaml"

err() {
	printf "\033[31;1merr: %b\033[0m\n" "$@"
}

early_escape_possible() {
	last_pnpm_time="$(git log -1 --format="%at" "$npm_lock_path")"
	last_bump_time="$(git log -1 --format="%at" "$nix_hash_path")"

	if [ -z "$last_bump_time" ] || [ -z "$last_pnpm_time" ] || [ "$last_bump_time" -lt "$last_pnpm_time" ]; then
		return 1
	else
		return 0
	fi
}

sanity_checks() {
	if [ ! -e "$nix_hash_path" ] || [ ! -e "$npm_lock_path" ]; then
		err "expected paths does not exists, are you sure you're running this inside git repo"
		exit 1
	fi

	if ! git diff-index --quiet --cached HEAD; then
		err "commit staged changes first"
		exit 1
	fi
}

new_hash_get() {
	cur_hash="$(cat "$nix_hash_path")"
	echo "$fake_hash" > "$nix_hash_path"

	out="$(mktemp)"
	nix build .#budcustomer.pnpmDeps -L > "$out" 2>&1
	tac "$out" | grep -Eom1 'sha256-[^=]*='

	rm "$out"
	echo "$cur_hash" > "$nix_hash_path"
}

##########
## MAIN ##
##########

# if early_escape_possible; then
# 	echo "early escape success, nix bump commit is newer"
# 	exit 0
# else
# 	echo "early escape not possible, npm bump commit is newer"
# fi

cur_hash="$(cat "$nix_hash_path")"
new_hash="$(new_hash_get)"
if [ "$cur_hash" != "$new_hash" ]; then
	echo "hash changed: ${cur_hash} -> ${new_hash}"
	echo "$new_hash" >"$nix_hash_path"

	git add "$nix_hash_path"
	git -c "user.name=$commit_author" -c "user.email=$commit_email" commit -m "$commit_message"
	git push
else
	echo "hash did not change: waiting for your next commit"
fi
