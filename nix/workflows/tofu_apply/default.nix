{
  writeShellApplication,
  sops,
  opentofu,
  jq,
  git,
  bash,
}:
writeShellApplication {
  name = "tofu_apply";

  runtimeInputs = [
    sops
    opentofu
    jq
    git
    bash
  ];

  text = builtins.readFile ./script.sh;
}
