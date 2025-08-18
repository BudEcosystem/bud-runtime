{
  writeShellApplication,
  qrencode,
  wireguard-tools,
}:
writeShellApplication {
  name = "bud_wg";

  runtimeInputs = [
    qrencode
    wireguard-tools
  ];

  text = builtins.readFile ./script.sh;
}
