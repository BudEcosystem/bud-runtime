{ config, lib, ... }:
let
  host = config.networking.hostName;
in
{
  imports = [
    ./modules/users.nix
  ];

  global.userdata = {
    email = "sinan@bud.studio";
    domain = "dev.bud.studio";
  };

  sops.defaultSopsFile = lib.mkForce ../${host}/secrets.yaml;
}
