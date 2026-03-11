{ pkgs, lib, ... }:
let
  privateCIDR4 = [
    "192.168.0.0/16"
    "10.0.0.0/8"
    "172.16.0.0/12"
  ];
  privateCIDR6 = [
    "fd00::/8"
  ];
  privateTCPPorts = [
    # HA with embedded etcd
    2379
    2380
    # K3s supervisor and Kubernetes API Server
    6443
    # Kubelet metrics
    10250
  ];
  privateUDPPorts = [
    # Flannel VXLAN
    8472
  ];

  allowCIDRPorts =
    cidrs: ports: proto: isIPv6:
    let
      cmd = if isIPv6 then "ip6tables" else "iptables";
    in
    lib.flatten (
      map (
        cidr:
        (map (
          port:
          "${cmd} -A nixos-fw --source ${cidr} -p ${proto} -m ${proto} --dport ${toString port} -j nixos-fw-accept"
        ) ports)
      ) cidrs
    );
in
{
  # k3s ingress
  networking.firewall = {
    allowedTCPPorts = [
      # http ingress
      80
      443
    ];

    extraCommands = lib.concatLines (
      (allowCIDRPorts privateCIDR4 privateUDPPorts "udp" false)
      ++ (allowCIDRPorts privateCIDR6 privateUDPPorts "udp" true)
      ++ (allowCIDRPorts privateCIDR4 privateTCPPorts "tcp" false)
      ++ (allowCIDRPorts privateCIDR6 privateTCPPorts "tcp" true)
    );
  };

  environment = {
    variables.KUBECONFIG = "/etc/rancher/k3s/k3s.yaml";
    systemPackages = with pkgs; [
      kubernetes-helm
      k9s
    ];
  };

  # for checkpoint/stove8s
  programs.criu.enable = true;
  systemd.services.k3s.path = [ pkgs.criu ];
  boot.kernel.sysctl."kernel.io_uring_disabled" = 2;
  environment.etc."criu/runc.conf".text = ''
    tcp-established
    link-remap
    timeout=3600
  '';

  services.k3s = {
    gracefulNodeShutdown.enable = true;
    enable = true;

    # extraFlags = [
    #   # can only enable IPv6 on fresh clusterInit
    #   "--cluster-cidr=10.42.0.0/16,fd12:b0d8:b00b::/56"
    #   "--service-cidr=10.43.0.0/16,fd12:b0d8:babe::/112"
    #   "--flannel-ipv6-masq"
    # ];

    # https://github.com/k3s-io/k3s/discussions/2997#discussioncomment-12315047
    manifests.traefik-daemonset = {
      enable = true;
      target = "traefik-daemonset.yaml";
      source = ./traefik-daemonset.yaml;
    };
  };
}
