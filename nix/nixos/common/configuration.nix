{ config, lib, ... }:
let
  host = config.networking.hostName;
in
{
  imports = [
    ./modules/users.nix
  ];

  networking.useDHCP = lib.mkForce true;
  sops.defaultSopsFile = lib.mkForce ../${host}/secrets.yaml;
}
