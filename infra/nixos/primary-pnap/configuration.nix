{ lib, ... }:
{
  imports = [
    ../primary-disk/configuration.nix
    ./modules/network.nix
  ];

  services.scid.settings.jobs = lib.mkForce { };
}
