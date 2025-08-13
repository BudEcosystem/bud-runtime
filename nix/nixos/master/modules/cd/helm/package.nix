{
  kubernetes-helm,
  writeShellApplication,
  sops,
  git,
  coreutils,
}:

writeShellApplication {
  name = "nixos-cd";

  runtimeInputs = [
    coreutils
    kubernetes-helm
    sops
    git
  ];

  text = builtins.readFile ./script.sh;
}
