{ config, ... }:
{
  sops.secrets."k3s_token" = { };

  services.k3s = {
    enable = true;
    role = "server";
    tokenFile = config.sops.secrets."k3s_token".path;
    clusterInit = true;
  };
}
