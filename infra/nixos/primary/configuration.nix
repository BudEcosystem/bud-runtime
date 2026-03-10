{
  imports = [
    ../common/configuration.nix
    ../budk8s/configuration.nix
    ../master/configuration.nix

    ./modules/scid.nix
  ];

  services.k3s.clusterInit = true;
}
