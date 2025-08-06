{ lib, ... }:

{
  imports = [
    ../common/configuration.nix
    ./hardware-configuration.nix
    ./disko.nix

    ./modules/k3s.nix
    ./modules/cd
    ./modules/wireguard.nix
  ];

  boot.loader.systemd-boot.enable = true;
  system.stateVersion = lib.mkForce "25.11";
}
