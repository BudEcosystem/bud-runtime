#!/bin/sh

export_sops_secret_silent() {
	k1="$1"
	k2="$2"
	var_name="$3"

	if var_value="$(sops --decrypt --extract "[\"""$k1""\"][\"""$k2""\"]" "infra/terraform/devbox/secrets.yaml")"; then
		export "$var_name"="$var_value"
	fi
}

export_sops_secret_silent s3 access_key AWS_ACCESS_KEY_ID
export_sops_secret_silent s3 secret_key AWS_SECRET_ACCESS_KEY

tofu -chdir=infra/terraform/devbox init
tofu -chdir=infra/terraform/devbox apply -auto-approve
