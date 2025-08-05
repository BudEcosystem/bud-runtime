{
  writeShellApplication,
  sops,
  opentofu,
  jq,
  git,
}:
writeShellApplication {
  name = "devbox_tofu_apply";

  runtimeInputs = [
    sops
    opentofu
    jq
    git
  ];

  text = builtins.readFile ./script.sh;
}
