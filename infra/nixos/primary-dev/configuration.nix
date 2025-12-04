{
  imports = [
    ../primary/configuration.nix
    ./disko.nix

    ./modules/scid.nix
    ./modules/wireguard.nix
  ];
}
