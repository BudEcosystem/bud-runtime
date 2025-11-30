{
  imports = [
    ../azure/configuration.nix
    ./modules/k3s
    ./modules/budk8s.nix
    ./modules/headscale
  ];

  # let cloud-init do that, uses hostname value from OpenTofu
  environment.etc.hostname.enable = false;
}
