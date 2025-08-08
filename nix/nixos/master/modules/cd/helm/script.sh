#!/bin/sh
set -e

repo="https://github.com/BudEcosystem/bud-runtime.git"
if [ ! -d "bud-runtime" ]; then
	git clone "$repo"
	cd bud-runtime
else
	cd bud-runtime
	git clean -fdx
	hash_cur="$(git log -n1 master --pretty=format:"%H")"
	git pull origin master
	hash_new="$(git log -n1 master --pretty=format:"%H")"

	if [ "$hash_cur" = "$hash_new" ]; then
		exit 0
	fi
fi

helm_path="$(git rev-parse --show-toplevel)/infra/helm"
for chart in "$helm_path"/*; do
	namespace="nixos-cd-$(basename "$chart")"
	release_name="panda"

	helm dependency update "$chart"
	if [ -r "$chart/values.enc.yaml" ]; then
		sops -d "$chart/values.enc.yaml" > "$chart/secrets.yaml"
	else
		echo "" > "$chart/secrets.yaml"
	fi

	# do not exit if a single chart fails
	set +e
	KUBECONFIG="/etc/rancher/k3s/k3s.yaml" helm upgrade \
		--install \
		--namespace "$namespace" \
		--create-namespace \
		--values "$chart/secrets.yaml" \
		"$release_name" "$chart"
	set -e
done
