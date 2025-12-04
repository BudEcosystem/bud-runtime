{
  imports = [
    ../master/configuration.nix
    ./disko.nix

    ./modules/scid.nix
    ./modules/nfs.nix
  ];

  services.k3s.clusterInit = true;
}
