{ lib, ... }:

{
  imports = [
    ../common/configuration.nix
    ./hardware-configuration.nix
    ./disko.nix

    ./modules/k3s.nix
  ];

  boot.loader.systemd-boot.enable = true;
  system.stateVersion = lib.mkForce "25.11";
}
