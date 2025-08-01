{
  writeShellApplication,
  sops,
  opentofu,
  jq,
}:
writeShellApplication {
  name = "bumper";

  runtimeInputs = [
    sops
    opentofu
    jq
  ];

  text = builtins.readFile ./script.sh;
}
