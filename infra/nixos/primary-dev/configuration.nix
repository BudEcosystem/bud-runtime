{
  imports = [
    ../primary/configuration.nix
    ../azure/configuration.nix
    ../dev/configuration.nix
    ../disk/configuration.nix
    ./disko.nix

    ./modules/scid
    ./modules/wireguard
    ./modules/nfs.nix
  ];
}
