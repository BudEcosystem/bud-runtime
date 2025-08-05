{
  self,
  mkShell,
  nixfmt-rfc-style,

  sops,
  age,

  k3d,
  kubectl,
  kubernetes-helm,
  helm-ls,
  openssl,

  yaml-language-server,
  nodejs,

  terraform-ls,
  opentofu,
  azure-cli,
  graphviz,
  jq, # nixos-anywhere terraform module

  shfmt,
  bash-language-server,
  pre-commit,
  ruff,
  mypy,
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
  ];

  shellHook = ''
    export_sops_secret_silent() {
        k1="$1"
        k2="$2"
        var_name="$3"

        if var_value="$(sops --decrypt --extract "[\""$k1"\"][\""$k2"\"]" "${self}/infra/terraform/devbox/secrets.yaml" )"
        then
            export "$var_name"="$var_value"
        fi
    }

    export_sops_secret_silent s3 access_key AWS_ACCESS_KEY_ID
    export_sops_secret_silent s3 secret_key AWS_SECRET_ACCESS_KEY

    export PS1="\033[0;35m[bud]\033[0m $PS1"
  '';
}
