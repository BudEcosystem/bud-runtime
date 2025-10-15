{ config, ... }:
let
  primaryIp = config.global.budk8s.primaryIp;
in
{
  imports = [ ../budk8s/configuration.nix ];

  boot.supportedFilesystems = [ "nfs" ];
  services.k3s = {
    role = "server";
    serverAddr = "https://${primaryIp}:6443";
  };

  # ingress nodes are not part of the scid job
  system.autoUpgrade = {
    enable = true;
    flake = "github:BudEcosystem/bud-runtime#ingress";
    flags = [ "-L" ];
    dates = "hourly";
  };
}
