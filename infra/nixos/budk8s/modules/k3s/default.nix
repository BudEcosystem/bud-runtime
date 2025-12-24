{ pkgs, ... }:
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

  environment = {
    variables.KUBECONFIG = "/etc/rancher/k3s/k3s.yaml";
    systemPackages = with pkgs; [
      kubernetes-helm
      k9s
    ];
  };

  # for checkpoint/stove8s
  systemd.services.k3s.path = [ pkgs.criu ];

  services.k3s = {
    gracefulNodeShutdown.enable = true;
    enable = true;

    extraFlags = [
      # can only enable IPv6 on fresh clusterInit
      # "--cluster-cidr=10.42.0.0/16,fd12:b0d8:b00b::/56"
      # "--service-cidr=10.43.0.0/16,fd12:b0d8:babe::/112"
      # "--flannel-ipv6-masq"
    ];

    # https://github.com/k3s-io/k3s/discussions/2997#discussioncomment-12315047
    manifests.traefik-daemonset = {
      enable = true;
      target = "traefik-daemonset.yaml";
      source = ./traefik-daemonset.yaml;
    };
  };
}
