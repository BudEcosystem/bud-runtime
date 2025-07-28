{ lib, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../common/configuration.nix
    ./modules/k3s.nix
  ];

  system.stateVersion = lib.mkForce "25.11";
  boot.loader.systemd-boot.enable = true;
}
