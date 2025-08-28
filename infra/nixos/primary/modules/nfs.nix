{ config, ... }:
let
  primaryIp = config.global.budk8s.primaryIp;
  nfsDataPath = config.diskio.devices.disk.nfs_data.content.partitions.nfs_data.content.mountpoint;
in
{
  networking.firewall.allowedTCPPorts = [ 2049 ];
  services.nfs.server = {
    enable = true;
    exports = ''
      ${nfsDataPath}  ${primaryIp}/24(rw,sync,no_subtree_check,no_root_squash)
    '';
  };
}
