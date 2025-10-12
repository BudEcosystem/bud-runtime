#!/bin/sh

bud_config_dir="${XDG_DATA_HOME:-$HOME/.config}/bud"
bud_share_dir="${XDG_DATA_HOME:-$HOME/.local/share}/bud"

bud_repo="https://github.com/BudEcosystem/bud-runtime.git"
bud_repo_local="$bud_share_dir/bud-runtime"
k3s_kubeconfig_path="/etc/rancher/k3s/k3s.yaml"

die() {
	printf "\033[31;1mErr: %b\033[0m\n" "${1:-no args for die()}" 1>&2
	exit "${2:-1}"
}

dir_ensure() {
	git clone "$bud_repo" "$bud_repo_local" || exit 1

	mkdir -p "$bud_config_dir"
	mkdir -p "$bud_share_dir"
}

k8s_is_installed() {
	if kubectl get ns >/dev/null 2>&1; then
		return 0
	fi

	if KUBECONFIG="$k3s_kubeconfig_path" kubectl get ns >/dev/null 2>&1; then
		export KUBECONFIG="$k3s_kubeconfig_path"
		return 0
	fi

	return 1
}
k3s_install() {
	curl -sfL https://get.k3s.io | sh -
	export KUBECONFIG="$k3s_kubeconfig_path"
}
k8s_ensure() {
	if ! k8s_is_installed; then
		k3s_install
	fi
}

helm_install() {
	name="$1"
	chart_path="$bud_repo_local/infra/helm/$name"
	scid_path="$chart_path/scid.toml"

	namespace="$(tq -f "$scid_path" -r '.namespace')"
	release_name="$(tq -f "$scid_path" -r '.release_name')"
	if tq -f "$scid_path" -r '.chart_path_override' >/dev/null 2>&1; then
		chart_path="$(tq -f "$scid_path" -r '.chart_path_override')"
	fi

	helm upgrade \
		--install \
		-n "$namespace" \
		--create-namespace \
		"$release_name" \
		"$chart_path" \
		-f "$chart_path/values.yaml" \
		"$@"
}

helm_ensure() {
	helm_install keel -f "$bud_repo_local/infra/helm/keel/example.noslack.yaml"
	helm_install dapr

	nvim "$bud_repo_local/infra/helm/bud/example.standalone.yaml"
	helm_install bud -f "$bud_repo_local/infra/helm/bud/example.standalone.yaml"
}

is_nixos() {
	if grep -q 'DISTRIB_ID=nixos' /etc/lsb-release >/dev/null 2>&1; then
		return 0
	fi
}

##########
## MAIN ##
##########

if is_nixos; then
	die "NixOS: Use the modules instead"
fi

dir_ensure
k8s_ensure
helm_ensure
