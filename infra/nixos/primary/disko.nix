{
  disko.devices = {
    disk = {
      nfs_disk = {
        device = "/dev/nvme0n2";
        type = "disk";
        content = {
          type = "gpt";
          partitions = {
            root = {
              size = "100%";
              content = {
                type = "filesystem";
                format = "ext4";
                mountpoint = "/nfs_disk";
              };
            };
          };
        };
      };
    };
  };
}
