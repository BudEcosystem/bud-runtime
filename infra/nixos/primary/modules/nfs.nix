{ config, ... }:
let
  primaryIp = config.global.budk8s.primaryIp;
  nfsRoot = config.disko.devices.disk.nfs_data.content.partitions.nfs_data.content.mountpoint;
  budk8sCsiRoot = "${nfsRoot}/budk8s-nfs-csi";
in
{
  networking.firewall.allowedTCPPorts = [ 2049 ];
  systemd.tmpfiles.rules = [ "d ${budk8sCsiRoot} - root root - -" ];

  services.nfs.server = {
    enable = true;
    exports = ''
      ${nfsRoot}        ${primaryIp}/24(rw,sync,no_subtree_check,no_root_squash,fsid=0,insecure)
      ${budk8sCsiRoot}  ${primaryIp}/24(rw,sync,no_subtree_check,no_root_squash,insecure)
    '';
  };
}
