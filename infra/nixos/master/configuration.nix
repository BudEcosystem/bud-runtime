{
  imports = [ ../budk8s/configuration.nix ];

  services.k3s = {
    role = "server";
    extraFlags = [
      "--write-kubeconfig-group users"
      "--write-kubeconfig-mode 0640"
    ];
  };
}
