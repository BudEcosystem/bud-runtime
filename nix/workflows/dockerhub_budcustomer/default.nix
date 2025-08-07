{
  writeShellApplication,
  coreutils,
  docker,
  nix,
  sops,
}:
writeShellApplication {
  name = "devbox_tofu_apply";

  runtimeInputs = [
    sops
    nix
    docker
    coreutils
  ];

  text = builtins.readFile ./script.sh;
}
