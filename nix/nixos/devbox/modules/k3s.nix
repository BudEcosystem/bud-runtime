{ config, ... }:
{
  imports = [ ./cd ];

  # k3s ingress
  networking.firewall.allowedTCPPorts = [
    80
    443
  ];

  sops.secrets."misc/k3s_token" = { };
  services.k3s = {
    enable = true;
    role = "server";
    tokenFile = config.sops.secrets."misc/k3s_token".path;
    clusterInit = true;
    extraFlags = [
      "--write-kubeconfig-group users"
      "--write-kubeconfig-mode 0640"
    ];
  };
}
