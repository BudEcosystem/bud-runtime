{
  imports = [ ../budk8s/configuration.nix ];
  services.k3s.serverAddr = "https://<ip of first node>:6443";
}
