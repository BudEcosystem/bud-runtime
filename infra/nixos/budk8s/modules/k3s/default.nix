{ config, pkgs, ... }:
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

  environment = {
    variables.KUBECONFIG = "/etc/rancher/k3s/k3s.yaml";
    systemPackages = [ pkgs.kubernets-helm ];
  };

  services.k3s = {
    gracefulNodeShutdown.enable = true;
    enable = true;
    role = "server";
    tokenFile = config.sops.secrets."k3s_server_token".path;

    extraKubeletConfig.maxPods = 512;
    extraFlags = [
      "--write-kubeconfig-group users"
      "--write-kubeconfig-mode 0640"
      "--disable local-storage"
    ];
  };
}
