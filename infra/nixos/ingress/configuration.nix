{ config, ... }:
let
  primaryIp = config.global.budk8s.primaryIp;
in
{
  imports = [
    ../common/configuration.nix
    ../dev/configuration.nix
    ../azure/configuration.nix
    ../budk8s/configuration.nix
    ../master/configuration.nix
  ];

  boot.supportedFilesystems = [ "nfs" ];
  services.k3s.serverAddr = "https://${primaryIp}:6443";

  # ingress nodes are not part of the scid job
  system.autoUpgrade = {
    enable = true;
    flake = "github:BudEcosystem/bud-runtime#ingress";
    flags = [ "-L" ];
    dates = "hourly";
  };
}
