{
  imports = [
    ../azure/configuration.nix
    ../budk8s/configuration.nix
    ../common/configuration.nix
  ];

  services.k3s = {
    role = "server";
    extraFlags = [
      "--disable local-storage"
      "--write-kubeconfig-group users"
      "--write-kubeconfig-mode 0640"
    ];
  };
}
