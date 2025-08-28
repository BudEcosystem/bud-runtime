{
  imports = [ ../budk8s/configuration.nix ];
  services.k3s.serverAddr = "https://10.177.2.69:6443";
}
