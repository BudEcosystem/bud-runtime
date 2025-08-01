{
  system.autoUpgrade = {
    enable = true;
    flake = "github:BudEcosystem/bud-runtime#devbox";
    flags = [ "-L" ];
    dates = "hourly";
  };
}
