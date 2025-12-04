{
  imports = [
    ../master/configuration.nix
    ../budk8s/configuration.nix
    ../azure/configuration.nix
    ../common/configuration.nix
    ./disko.nix

    ./modules/scid.nix
    ./modules/wireguard.nix
    ./modules/docker.nix
    ./modules/nfs.nix
  ];

  services.k3s.clusterInit = true;
}
