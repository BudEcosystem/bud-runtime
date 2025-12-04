{ config, lib, ... }:
let
  host = config.networking.hostName;
in
{
  imports = [
    ./modules/users.nix
    ./disko.nix
  ];

  global.userdata = {
    email = "sinan@bud.studio";
    domain = "bud.studio";
  };

  sops.defaultSopsFile = lib.mkForce ../${host}/secrets.yaml;
  facter.reportPath = ../${host}/facter.json;
  system.stateVersion = lib.mkForce "25.11";
}
