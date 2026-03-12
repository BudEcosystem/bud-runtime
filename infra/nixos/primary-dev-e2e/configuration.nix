{ lib, ... }:
{
  imports = [
    ../primary/configuration.nix
    ../dev/configuration.nix
    ./disko.nix

    ./modules/scid
    ./modules/wireguard
  ];

  facter.reportPath = ./facter.json;

  programs.nix-ld.enable = true;

  boot.loader = {
    systemd-boot.enable = lib.mkForce false;
    grub.enable = true;
  };
}
