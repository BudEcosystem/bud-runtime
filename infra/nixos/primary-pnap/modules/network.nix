{ ... }:
{
  services.cloud-init = {
    enable = true;
    network.enable = true;
  };
  networking.useNetworkd = true;
}
