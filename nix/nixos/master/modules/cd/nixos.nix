{
  system.autoUpgrade = {
    enable = true;
    flake = "github:BudEcosystem/bud-runtime#master";
    flags = [ "-L" ];
    dates = "hourly";
  };
}
