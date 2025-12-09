{ ... }:
let
  nfsRoot = "/nfs_data";
  budk8sCsiRoot = "${nfsRoot}/budk8s-nfs-csi";
in
{
  networking.firewall.allowedTCPPorts = [ 2049 ];
  systemd.tmpfiles.rules = [ "d ${budk8sCsiRoot} - root root - -" ];

  services.nfs.server = {
    enable = true;
    exports = ''
      ${nfsRoot}        *(rw,sync,no_subtree_check,no_root_squash,fsid=0,insecure)
      ${budk8sCsiRoot}  *(rw,sync,no_subtree_check,no_root_squash,insecure)
    '';
  };
}
