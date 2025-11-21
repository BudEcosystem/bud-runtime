{
  writeShellApplication,

  kubernetes-helm,
  kubectl,
  gnugrep,
  git,
  curl,
  tomlq,
  yq,
  vim,
  kmod,
  pciutils,
}:
writeShellApplication {
  name = "k8s_deploy";

  runtimeInputs = [
    kubernetes-helm
    kubectl
    gnugrep
    git
    curl
    tomlq
    vim
    kmod
    pciutils
    yq
  ];

  text = builtins.readFile ./script.sh;
}
