{
  global.disk.master = "vda";

  disko.devices.disk.k3s_storage = {
    device = "/dev/vdb";
    type = "disk";
    content = {
      type = "gpt";
      partitions.k3s_storage = {
        size = "100%";
        content = {
          type = "filesystem";
          format = "ext4";
          mountpoint = "/var/lib/rancher/k3s/storage";
        };
      };
    };
  };
}
