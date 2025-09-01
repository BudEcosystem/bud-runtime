{
  imports = [
    ../azure/configuration.nix
    ./modules/k3s
    ./modules/budk8s.nix
  ];
}
