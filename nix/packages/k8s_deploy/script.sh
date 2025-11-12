#!/bin/sh

set -o xtrace
set +o nounset

bud_config_dir="${XDG_DATA_HOME:-$HOME/.config}/bud"
bud_share_dir="${XDG_DATA_HOME:-$HOME/.local/share}/bud"

bud_repo="https://github.com/BudEcosystem/bud-runtime.git"
bud_repo_local="$bud_share_dir/bud-runtime"
k3s_kubeconfig_path="/etc/rancher/k3s/k3s.yaml"

print_usage() {
	printf "%s (runtime|nvidia)" "${0##*/}"
}

die() {
	printf "\033[31;1mErr: %b\033[0m\n" "${1:-no args for die()}" 1>&2
	exit "${2:-1}"
}

is_k3s() {
	[ -f "$k3s_kubeconfig_path" ]
}
is_nixos() {
	grep -q 'DISTRIB_ID=nixos' /etc/lsb-release >/dev/null 2>&1
}

dir_ensure() {
	if [ -d "$bud_repo_local" ]; then
		output="$(git -C "$bud_repo_local" stash push)" || exit 1
		git -C "$bud_repo_local" pull || exit 1

		if ! echo "$output" | grep -q 'No local changes to save'; then
			git -C "$bud_repo_local" stash pop || exit 1
		fi
	else
		git clone "$bud_repo" "$bud_repo_local" || exit 1
	fi

	mkdir -p "$bud_config_dir"
	mkdir -p "$bud_share_dir"
}

k8s_is_installed() {
	if kubectl get ns >/dev/null 2>&1; then
		return 0
	fi

	sudo chown "$(whoami)" "$k3s_kubeconfig_path" >/dev/null 2>&1
	if KUBECONFIG="$k3s_kubeconfig_path" kubectl get ns >/dev/null 2>&1; then
		export KUBECONFIG="$k3s_kubeconfig_path"
		return 0
	fi

	return 1
}
k3s_install() {
	curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--write-kubeconfig-group $(id -gn) --write-kubeconfig-mode 0640" sh -
	export KUBECONFIG="$k3s_kubeconfig_path"
}
k8s_clusterrole_exists() {
	kubectl get clusterrole "$1" >/dev/null 2>&1
}
k8s_apiresources_exists() {
	name="$1"
	api_version="$2"
	kubectl api-resources | grep -q "${name}[[:space:]]+[a-z,]*[[:space:]]*${api_version}" >/dev/null 2>&1
}
k8s_ensure() {
	if ! k8s_is_installed; then
		if is_nixos; then
			die "NixOS: Use the k3s modules instead to setup k8s"
		else
			k3s_install
		fi
	fi
}

helm_install() {
	name="$1"
	namespace_and_releasename="$2"
	shift 2

	chart_path="$bud_repo_local/infra/helm/$name"
	values_path="$chart_path/values.yaml"
	scid_path="$chart_path/scid.toml"

	if [ -z "$namespace_and_releasename" ]; then
		namespace="$(tq -f "$scid_path" '.namespace')"
		release_name="$(tq -f "$scid_path" '.release_name')"
	else
		namespace="$namespace_and_releasename"
		release_name="$namespace_and_releasename"
	fi

	if tq -f "$scid_path" '.chart_path_override' >/dev/null 2>&1; then
		chart_path="$chart_path/$(tq -f "$scid_path" '.chart_path_override')"
	fi

	helm upgrade \
		--install \
		-n "$namespace" \
		--create-namespace \
		"$release_name" \
		"$chart_path" \
		-f "$values_path" \
		"$@"
}
helm_ensure() {
	if ! k8s_clusterrole_exists keel; then
		helm_install keel "" -f "$bud_repo_local/infra/helm/keel/example.noslack.yaml"
	fi

	if ! k8s_apiresources_exists 'components' 'dapr.io/v1alpha1'; then
		helm_install dapr ""
	fi

	if ! k8s_apiresources_exists 'certificates' 'cert-manager.io/v1'; then
		kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.19.1/cert-manager.yaml
		helm_install cert-manager "" --skip-crds
	fi

	vim "$bud_repo_local/infra/helm/bud/example.standalone.yaml"
	helm_install bud bud \
		-f "$bud_repo_local/infra/helm/bud/example.standalone.yaml" \
		-f "$bud_repo_local/infra/helm/bud/example.secrets.yaml"
}

nvidia_ensure() {
	if k8s_clusterrole_exists nvidia-operator-validator; then
		return
	fi

	if ! lspci | grep NVIDIA -q >/dev/null 2>&1; then
		die "No Nvidia devices detected"
	fi

	flags=""
	if lsmod | grep -q nvidia >/dev/null 2>&1; then
		flags="$flags --set driver.enabled=false"
	fi
	if is_k3s; then
		flags="$flags --set toolkit.env[0].name=CONTAINERD_CONFIG"
		flags="$flags --set toolkit.env[0].value=/var/lib/rancher/k3s/agent/etc/containerd/config.toml"
		flags="$flags --set toolkit.env[1].name=CONTAINERD_SOCKET"
		flags="$flags --set toolkit.env[1].value=/run/k3s/containerd/containerd.sock"
	fi

	helm repo add gpu-operator https://helm.ngc.nvidia.com/nvidia
	# shellcheck disable=SC2086
	helm upgrade \
		--install \
		-n gpu-operator --create-namespace \
		gpu-operator gpu-operator/gpu-operator \
		--version 25.3.4 \
		$flags
}

traefik_ensure() {
	if k8s_clusterrole_exists traefik-kube-system; then
		return
	fi

	helm repo add traefik https://traefik.github.io/charts
	helm upgrade \
		--install \
		-n traefik --create-namespace \
		traefik traefik/traefik
}

##########
## MAIN ##
##########

case "$1" in
runtime)
	dir_ensure
	k8s_ensure
	traefik_ensure
	helm_ensure
	;;
nvidia)
	k8s_ensure
	nvidia_ensure
	;;
"")
	print_usage
	exit 0
	;;
*)
	die "Invalid command: $1"
	;;
esac
