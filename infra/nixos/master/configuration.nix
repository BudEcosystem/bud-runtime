{
  imports = [ ../budk8s/configuration.nix ];

  services.k3s = {
    role = "server";
    extraFlags = [
      "--disable local-storage"
      "--write-kubeconfig-group users"
      "--write-kubeconfig-mode 0640"
    ];
  };
}
