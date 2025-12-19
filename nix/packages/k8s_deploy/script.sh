#!/bin/sh

set -o xtrace
set +o nounset

bud_config_dir="${XDG_DATA_HOME:-$HOME/.config}/bud"
bud_share_dir="$HOME/.local/share/bud"
bud_override_yaml="$bud_share_dir/bud.override.yaml"

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
	kubectl api-resources | grep -Eq "${name}[[:space:]]+[a-z,]*[[:space:]]*${api_version}" >/dev/null 2>&1
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

helm_ensure() {
	scid_config="$(mktemp --suffix=.budk8sdeploy)"
	cat <<-EOF >"$scid_config"
		branch = "master"
		repo_url = "https://github.com/BudEcosystem/bud-runtime.git"

		[helm]
		charts_path = "infra/helm"
		env = "prod"
	EOF

	if [ ! -r "$bud_override_yaml" ]; then
		curl "https://raw.githubusercontent.com/BudEcosystem/bud-runtime/refs/heads/master/infra/helm/bud/example.standalone.yaml" >"$bud_override_yaml"
	fi
	vim "$bud_override_yaml"

	cd "$bud_share_dir" || return 1
	SCID_CONFIG="$scid_config" scid --force-re-run
	cd - || return 1
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
	if k8s_apiresources_exists 'middlewares' 'traefik.io/v1alpha1'; then
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
