{
  writeShellApplication,

  kubernetes-helm,
  kubectl,
  gnugrep,
  git,
  curl,
  tomlq,
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
  ];

  text = builtins.readFile ./script.sh;
}
