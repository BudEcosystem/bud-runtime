{ config, ... }:
{
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

    extraKubeletConfig.maxPods = 512;
    extraFlags = [
      "--write-kubeconfig-group users"
      "--write-kubeconfig-mode 0640"
    ];

    # TODO: upstream bug
    # error: undefined variable 'yq-go'
    # at /nix/store/bgl6ldj5ihbwcq8p42z3a0qzgqafgk2b-source/nixos/modules/services/cluster/k3s/default.nix:43:74:
    #     42|       readFile (
    #     43|         pkgs.runCommand "${path}-converted.json" { nativeBuildInputs = [ yq-go ]; } ''
    #       |                                                                          ^
    #     44|           yq --no-colors --output-format json ${path} > $out
    # autoDeployCharts = {
    #   dapr = {
    #     createNamespace = true;
    #     targetNamespace = "dapr-system";
    #     package = ./charts/dapr/dapr-1.15.9.tgz;
    #     values = ./charts/dapr/values.yaml;
    #   };
    #   cert-manager = {
    #     createNamespace = true;
    #     targetNamespace = "cert-manager";
    #     package = ./charts/cert-manager/cert-manager-v1.18.2.tgz;
    #     values = ./charts/cert-manager/values.yaml;
    #   };
    # };
  };
}
