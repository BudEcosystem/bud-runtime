{
  imports = [
    ./modules/k3s
    ./modules/budk8s.nix
  ];

  # let cloud-init do that, uses hostname value from OpenTofu
  environment.etc.hostname.enable = false;
}
