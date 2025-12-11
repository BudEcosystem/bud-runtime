{ lib, ... }:
{
  services.scid.jobs.NixOS = {
    exec_line = lib.mkForce [
      "nixos-rebuild"
      "switch"
      "--flake"
      ".#primary-disk"
      "-L"
    ];
    watch_paths = [
      "infra/nixos/primary-disk"
    ];
  };
}
