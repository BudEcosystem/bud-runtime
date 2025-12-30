{
  writeShellApplication,

  kubernetes-helm,
  kubectl,
  gnugrep,
  git,
  curl,
  vim,
  kmod,
  pciutils,
  scid,
}:
writeShellApplication {
  name = "k8s_deploy";

  runtimeInputs = [
    kubernetes-helm
    kubectl
    gnugrep
    git
    curl
    vim
    kmod
    pciutils
    scid
  ];

  text = builtins.readFile ./script.sh;
}
