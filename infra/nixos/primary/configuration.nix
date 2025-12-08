{
  imports = [
    ../common/configuration.nix
    ../dev/configuration.nix
    ../budk8s/configuration.nix
    ../master/configuration.nix

    ./modules/scid.nix
    ./modules/nfs.nix
  ];

  services.k3s.clusterInit = true;
}
