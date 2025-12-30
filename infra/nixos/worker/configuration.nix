{ config, ... }:
let
  primaryIp = config.global.budk8s.primaryIp;
in
{
  imports = [
    ../azure/configuration.nix
    ../budk8s/configuration.nix
    ../common/configuration.nix
    ../dev/configuration.nix
    ../disk/configuration.nix
  ];

  boot.supportedFilesystems = [ "nfs" ];
  services.k3s = {
    role = "agent";
    serverAddr = "https://${primaryIp}:6443";
  };

  # worker nodes are not part of the scid job
  system.autoUpgrade = {
    enable = true;
    flake = "github:BudEcosystem/bud-runtime#worker";
    flags = [ "-L" ];
    dates = "hourly";
  };

  facter.reportPath = ./facter.json;
}
