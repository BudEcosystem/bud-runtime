{
  imports = [
    ./hardware-configuration.nix
    ../common/configuration.nix
  ];

  boot.loader.systemd-boot.enable = true;
}
