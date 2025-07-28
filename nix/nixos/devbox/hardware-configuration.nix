{
  imports = [ ./disko.nix ];
  boot.kernelModules = [ "kvm-amd" ];
  virtualisation.hypervGuest.enable = true;
}
