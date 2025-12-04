{ config, lib, ... }:
let
  host = config.networking.hostName;
in
{
  imports = [
    ./disko.nix
  ];

  global.userdata = {
    email = "sinan@bud.studio";
    domain = "bud.studio";
  };

  sops.defaultSopsFile = lib.mkForce ../${host}/secrets.yaml;
  facter.reportPath = ../${host}/facter.json;
  system.stateVersion = lib.mkForce "25.11";
  # let cloud-init do that
  environment.etc.hostname.enable = false;

  # we assume all the systems have EFI support
  # change if needed in the future
  boot.loader = {
    systemd-boot.enable = true;
    timeout = 0;
  };
}
