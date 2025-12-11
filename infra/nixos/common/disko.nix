{ config, ... }:
let
  disk = config.global.disk.master;
in
{
  disko.devices = {
    disk = {
      os = {
        type = "disk";
        device = "/dev/${disk}";
        content = {
          type = "gpt";
          partitions = {
            ESP = {
              name = "ESP";
              label = "ESP";
              size = "1G";
              type = "EF00";
              priority = 100;
              content = {
                type = "filesystem";
                format = "vfat";
                extraArgs = [
                  "-F"
                  "32"
                  "-n"
                  "ESP"
                ];
                mountpoint = "/boot";
                mountOptions = [
                  "defaults"
                  "umask=0077"
                ];
              };
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
    };
  };
}
