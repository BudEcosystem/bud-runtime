{
  self,
  mkShell,
  nixfmt-rfc-style,
  sops,

  k3d,
  kubectl,
  kubernetes-helm,
  helm-ls,
  yaml-language-server,
  openssl,

  terraform-ls,
  opentofu,
  azure-cli,
  shfmt,
  bash-language-server,
  jq, # nixos-anywhere terraform module
}:

mkShell {
  buildInputs = [
    k3d
    kubectl
    kubernetes-helm
    helm-ls
    yaml-language-server
    openssl
    sops

    nixfmt-rfc-style

    terraform-ls
    opentofu
    azure-cli
    shfmt
    bash-language-server
    jq
  ];

  shellHook = ''
    export_sops_secret_silent() {
        k1="$1"
        k2="$2"
        var_name="$3"

        if var_value="$(sops --decrypt --extract "[\""$k1"\"][\""$k2"\"]" "${self}/secrets.yaml" 2> /dev/null)"
        then
            export "$var_name"="$var_value"
        fi
    }

    export_sops_secret_silent terraform access_key AWS_ACCESS_KEY_ID
    export_sops_secret_silent terraform secret_key AWS_SECRET_ACCESS_KEY

    export PS1="\033[0;35m[bud-infra]\033[0m $PS1"
  '';
}
