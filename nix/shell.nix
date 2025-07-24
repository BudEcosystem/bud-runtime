{
  mkShell,
  k3d,
  kubectl,
  kubernetes-helm,
  helm-ls,
  yaml-language-server,
  openssl,
  sops,
  nixfmt-rfc-style,
  terraform-ls,
  opentofu,
  azure-cli,
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
  ];

  shellHook = ''
    export PS1="\033[0;35m[bud-infra]\033[0m $PS1"
  '';
}
