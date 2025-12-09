{
  disko.devices = {
    disk = {
      nfs_data = {
        device = "/dev/nvme0n2";
        type = "disk";
        content = {
          type = "gpt";
          partitions = {
            nfs_data = {
              size = "100%";
              content = {
                type = "filesystem";
                format = "ext4";
                mountpoint = "/nfs_data";
              };
            };
          };
        };
      };
    };
  };
}
