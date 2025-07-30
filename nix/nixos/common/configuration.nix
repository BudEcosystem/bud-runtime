{ config, lib, ... }:
let
  host = config.networking.hostName;
in
{
  imports = [
    ./modules/users.nix
  ];

  sops.defaultSopsFile = lib.mkForce ../${host}/secrets.yaml;
}
