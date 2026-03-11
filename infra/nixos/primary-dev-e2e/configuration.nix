{
  imports = [
    ../primary/configuration.nix
    ../dev/configuration.nix
    ../disk/configuration.nix
    ./disko.nix

    ./modules/scid
    ./modules/wireguard
  ];

  facter.reportPath = ./facter.json;
}
