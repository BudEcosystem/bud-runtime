{
  writeShellApplication,

  kubernetes-helm,
  kubectl,
  gnugrep,
  git,
  curl,
  tomlq,
  vim,
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
  ];

  text = builtins.readFile ./script.sh;
}
