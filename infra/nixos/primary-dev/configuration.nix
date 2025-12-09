{
  imports = [
    ../primary/configuration.nix
    ../azure/configuration.nix
    ../dev/configuration.nix
    ./disko.nix

    ./modules/scid.nix
    ./modules/wireguard.nix
  ];
}
