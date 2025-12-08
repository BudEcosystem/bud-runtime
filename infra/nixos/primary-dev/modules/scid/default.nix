{
  config,
  lib,
  ...
}:
let
  sops_key_path = "/var/lib/sops-nix/key.txt";
in
{
  sops.secrets."misc/slack_token".sopsFile = ./secrets.yaml;

  services.scid = {
    enable = true;
    environment.SOPS_AGE_KEY_FILE = sops_key_path;
    settings = {
      tag = lib.mkForce null;

      slack = {
        channel = "infra";
        token = "%file%:${config.sops.secrets."misc/slack_token".path}";
      };

      jobs = {
        NixOS = {
          exec_line = lib.mkForce [
            "nixos-rebuild"
            "switch"
            "--flake"
            ".#primary-dev"
            "-L"
          ];
          watch_paths = [
            "infra/nixos/primary-dev"
          ];
        };
        OpenTofu = {
          name = "OpenTofu";
          slack_color = "#fbdb1c";
          exec_line = [
            "nix"
            "run"
            ".#workflow_tofu_apply"
            "-L"
          ];
          watch_paths = [
            "flake.nix"
            "flake.lock"
            "infra/tofu"
            "nix/workflows/tofu_apply"
          ];
        };
      };
    };
  };
}
