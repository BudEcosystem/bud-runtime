{ pkgs, lib, ... }:
{
  services.scid = {
    enable = true;

    environment = {
      KUBECONFIG = "/etc/rancher/k3s/k3s.yaml";
      HOME = "/var/lib/scid";
    };
    path = with pkgs; [
      kubernetes-helm
      nixos-rebuild
      nix
    ];

    settings = {
      branch = "master";
      repo_url = "https://github.com/BudEcosystem/bud-runtime.git";
      tag.model = "semver";
      helm = {
        env = lib.mkDefault "prod";
        charts_path = "infra/helm";
      };

      jobs.NixOS = {
        name = "NixOS";
        slack_color = "#7bb8e2";
        exec_line = [
          "nixos-rebuild"
          "switch"
          "--flake"
          ".#primary"
          "-L"
        ];
        watch_paths = [
          "flake.nix"
          "flake.lock"
          "infra/nixos/azure"
          "infra/nixos/budk8s"
          "infra/nixos/common"
          "infra/nixos/primary"
          "infra/nixos/master"
        ];
      };
    };
  };
}
