#!/bin/sh

set -e

repo_root="$(git rev-parse --show-toplevel)"
tofu_path="$repo_root/infra/tofu/$1"

export_sops_secret_silent() {
	k1="$1"
	k2="$2"
	var_name="$3"

	if var_value="$(sops --decrypt --extract "[\"""$k1""\"][\"""$k2""\"]" "$tofu_path/secrets.yaml")"; then
		export "$var_name"="$var_value"
	fi
}

if [ "$#" -ne 1 ]; then
	echo "Usage: ${0} <tofu_package>" >&2
	exit 1
elif [ ! -d "$tofu_path" ]; then
	echo "Error: No such directory: $tofu_path" >&2
	exit 1
fi

export_sops_secret_silent s3 access_key AWS_ACCESS_KEY_ID
export_sops_secret_silent s3 secret_key AWS_SECRET_ACCESS_KEY

tofu -chdir="$tofu_path" init
tofu -chdir="$tofu_path" apply -auto-approve
