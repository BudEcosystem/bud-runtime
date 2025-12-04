{ config, ... }:
let
  headScaleUrl = "https://headscale.sinanmohd.com";
  user = "sinan";
in
{
  sops.secrets."pre_auth_key".sopsFile = ./secrets.yaml;
  networking.firewall.trustedInterfaces = [ config.services.tailscale.interfaceName ];

  services.tailscale = {
    enable = true;
    interfaceName = "headscale";
    openFirewall = true;

    authKeyFile = config.sops.secrets."pre_auth_key".path;
    extraUpFlags = [
      "--login-server=${headScaleUrl}"
    ];
    extraSetFlags = [
      "--operator=${user}"
    ];
  };
}
