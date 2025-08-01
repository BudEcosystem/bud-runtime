{ config, ... }:
{
  sops.secrets."misc/k3s_token" = { };

  # k3s ingress
  networking.firewall.allowedTCPPorts = [
    80
    443
  ];

  services.k3s = {
    enable = true;
    role = "server";
    tokenFile = config.sops.secrets."misc/k3s_token".path;
    clusterInit = true;
  };
}
