{
  config,
  lib,
  ...
}:
{
  sops.secrets."k3s_server_token".sopsFile = ./secrets.yaml;

  services.k3s = {
    tokenFile = config.sops.secrets."k3s_server_token".path;
    extraKubeletConfig.maxPods = 512;
    extraFlags = lib.mkForce [ ];
  };
}
