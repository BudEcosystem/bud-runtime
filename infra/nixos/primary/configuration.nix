{
  imports = [
    ../budk8s/configuration.nix
    ./disko.nix

    ./modules/scid.nix
    ./modules/wireguard.nix
    ./modules/docker.nix
  ];

  services.k3s.clusterInit = true;
}
