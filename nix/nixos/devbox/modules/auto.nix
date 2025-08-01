{
  system.autoUpgrade = {
    enable = true;
    flake = "github:budstudio/bud-runtime#devbox";
    flags = [ "-L" ];
    dates = "hourly";
  };
}
