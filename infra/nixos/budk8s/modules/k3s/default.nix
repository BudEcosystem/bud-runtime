{ config, ... }:
{
  # k3s ingress
  networking.firewall = {
    # Flannel VXLAN
    allowedUDPPorts = [ 8472 ];

    allowedTCPPorts = [
      # http ingress
      80
      443
      # HA with embedded etcd
      2379
      2380
      # K3s supervisor and Kubernetes API Server
      6443
      # Kubelet metrics
      10250
    ];
  };

  sops.secrets."k3s_server_token".sopsFile = ./secrets.yaml;

  services.k3s = {
    enable = true;
    role = "server";
    tokenFile = config.sops.secrets."k3s_server_token".path;

    extraKubeletConfig.maxPods = 512;
    extraFlags = [
      "--write-kubeconfig-group users"
      "--write-kubeconfig-mode 0640"
    ];
  };
}
