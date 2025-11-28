{
  self,
  mkShell,
  nixfmt-rfc-style,
  markdownlint-cli,

  sops,
  age,
  gnugrep,
  git,
  callPackage,

  k3d,
  kubectl,
  kubernetes-helm,
  helm-ls,
  openssl,

  yaml-language-server,
  nodejs,
  pnpm,

  terraform-ls,
  opentofu,
  azure-cli,
  graphviz,
  jq, # nixos-anywhere terraform module

  shfmt,
  bash-language-server,
  typescript-language-server,
  prefetch-npm-deps,
  pre-commit,
  ruff,
  mypy,
  pyright,
}:
let
  bud_wg = (callPackage ./bud_wg { });
in
mkShell {
  buildInputs = [
    k3d
    kubectl
    kubernetes-helm
    helm-ls
    yaml-language-server
    openssl
    sops
    age
    nixfmt-rfc-style
    terraform-ls
    opentofu
    azure-cli
    shfmt
    bash-language-server
    jq
    pre-commit
    nodejs
    graphviz
    ruff
    mypy
    typescript-language-server
    prefetch-npm-deps
    gnugrep
    git
    pyright
    bud_wg
    pnpm
    markdownlint-cli
  ];

  shellHook = ''
    bud_temp_path="$(mktemp -d)"
    cleanup_on_exit() {
        rm -rf "$bud_temp_path"
    }
    trap cleanup_on_exit EXIT

    # deploy development environment
    bud_pde() {
        if [ "$#" -lt 1 ]; then
            echo "Usage: pde <dev_name>"
            return 1
        fi
        dev_name="$1"

        chart="$(git rev-parse --show-toplevel)/infra/helm/bud" || return 1
        sops -d "$chart/values.enc.yaml" > "$chart/secrets.yaml" || return 1
        helm upgrade \
            --install \
            --namespace "pde-$dev_name" \
            --create-namespace \
            --values "$chart/secrets.yaml" \
            --values "$chart/values.pde.yaml" \
            --values "$chart/values.$dev_name.yaml" \
            "$dev_name" "$chart"
    }

    # setup sops, generate age key pair if not exists, return pubic key
    bud_sops() {
        if [ -n "$XDG_CONFIG_HOME" ]; then
                key_path="$XDG_CONFIG_HOME/sops/age/keys.txt"
        else
                case "$(uname -s)" in
                Linux)
                        key_path="$HOME/.config/sops/age/keys.txt"
                        ;;
                Darwin)
                        key_path="$HOME/Library/Application Support/sops/age/keys.txt"
                        ;;
                *)
                        echo "Unsupported System"
                        return 1
                        ;;
                esac
        fi

        mkdir -p "$(dirname "$key_path")" || return 1
        if [ ! -f "$key_path" ]; then
                age-keygen -o "$key_path" || return 1
        else
                printf "Public key: %s\n" "$(grep -Eom1 "age1.*$" "$key_path")"
        fi
    }

    bud_sops_sync() {
        for sec in $(find -name secrets.yaml) $(find -name '*.enc.yaml'); do
                sops updatekeys "$sec"
        done
    }

    budk8s_import() {

        if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
            echo "Usage: budk8s_import <repo/image:tag> [username]"
            return 1
        fi

        budk8s="primary.k8s.bud.studio"
        if [ "$2" != "" ]; then
            ssh_host="$budk8s"
        else
            ssh_host="$2@$budk8s"
        fi

        local_endpoint="$(mktemp)" || return 1
        docker save "$1" > "$local_endpoint" || return 1

        budk8s_endpoint="$(ssh "$ssh_host" mktemp)" || return 1
        scp "$local_endpoint" "$ssh_host:$budk8s_endpoint" || return 1
        ssh "$ssh_host" sudo ctr images import "$budk8s_endpoint" || return 1

        rm "$local_endpoint"
        ssh "$ssh_host" rm "$budk8s_endpoint"
    }

    export_sops_secret_silent() {
        k1="$1"
        k2="$2"
        var_name="$3"

        if var_value="$(sops --decrypt --extract "[\""$k1"\"][\""$k2"\"]" "${self}/infra/tofu/budk8s/secrets.yaml" 2> /dev/null)"
        then
            export "$var_name"="$var_value"
        fi
    }

    # terraform state handling
    export_sops_secret_silent s3 access_key AWS_ACCESS_KEY_ID
    export_sops_secret_silent s3 secret_key AWS_SECRET_ACCESS_KEY

    # budk8s access
    budk8s_tailscale_host="budk8s-primary"
    budk8s_wireguard_ip="10.54.132.1"
    if sops -d ${./budk8s.kubeconfig.enc.yaml} > "$bud_temp_path/kube.config" 2> /dev/null; then
        export KUBECONFIG="$bud_temp_path/kube.config"
        if tailscale status 2>/dev/null | grep -q "$budk8s_tailscale_host"; then
            sed -i "s/$budk8s_wireguard_ip/$budk8s_tailscale_host/g" "$bud_temp_path/kube.config"
        fi
    fi

    # eye candy
    export PS1="\033[0;35m[bud]\033[0m $PS1"
  '';
}
