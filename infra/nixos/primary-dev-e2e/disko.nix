{ config, ... }:
let
  disk = config.global.disk.master;
in
{
  global.disk.master = "vda";

  disko.devices.disk = {
    os = {
      type = "disk";
      device = "/dev/${disk}";
      content = {
        type = "gpt";
        partitions = {
          boot = {
            size = "1M";
            type = "EF02";
            priority = 100;
          };
          root = {
            name = "root";
            label = "root";
            size = "100%";
            priority = 200;
            content = {
              type = "filesystem";
              format = "ext4";
              mountpoint = "/";
            };
          };
        };
      };
    };

    k3s_storage = {
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
  };
}
