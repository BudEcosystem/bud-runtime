{ config, pkgs, ... }:
let
  sops_key_path = "/var/secrets/master.sops";
in {
  sops.secrets."misc/slack_token" = { };

  services.scid = {
    enable = true;

    environment = {
      SOPS_AGE_KEY_FILE = sops_key_path;
      KUBECONFIG = "/etc/rancher/k3s/k3s.yaml";
      HOME = "/var/lib/scid";
    };
    path = with pkgs; [
      kubernetes-helm
      nixos-rebuild
      nix
    ];

    settings = {
      repo_url = "https://github.com/BudEcosystem/bud-runtime.git";
      branch = "master";
      helm_charts_path = "infra/helm";

      slack = {
        channel = "infratest";
        token = "%file%:${config.sops.secrets."misc/slack_token".path}";
      };

      jobs = [
        {
          name = "NixOS";
          slack_color = "#7bb8e2";
          exec_line = [ "nixos-rebuild" "switch" "--flake" ".#master" "-L" ];
          watch_paths = [
            "flake.nix"
            "flake.lock"
            "nix/nixos"
          ];
        }
        {
          name = "OpenTofu";
          slack_color = "#fbdb1c";
          exec_line = [ "nix" "run" ".#workflow_tofu_apply" "-L" ];
          watch_paths = [
            "flake.nix"
            "flake.lock"
            "nix/workflows/tofu_apply"
          ];
        }
      ];
    };
  };
}
