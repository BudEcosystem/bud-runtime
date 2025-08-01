{ lib, pkgs, ... }:

{
  imports = [
    ../common/configuration.nix
    ./hardware-configuration.nix
    ./disko.nix

    ./modules/k3s.nix
    ./modules/wireguard.nix
    ./modules/auto.nix
  ];

  boot.loader.systemd-boot.enable = true;
  system.stateVersion = lib.mkForce "25.11";
  environment.systemPackages = [ pkgs.kubectl ];
}
