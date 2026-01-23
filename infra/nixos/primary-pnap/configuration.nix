{ lib, ... }:
{
  imports = [
    ../primary/configuration.nix
    ../disk/configuration.nix
    ./modules/network.nix
  ];

  services.scid.settings.jobs = lib.mkForce { };
}
