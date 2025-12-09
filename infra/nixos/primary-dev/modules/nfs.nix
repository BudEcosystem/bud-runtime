{ config, lib, ... }:
let
  primaryIp = config.global.budk8s.primaryIp;
  nfsRoot = "/nfs_data";
  budk8sCsiRoot = "${nfsRoot}/budk8s-nfs-csi";
in
{
  services.nfs.server.exports = lib.mkForce ''
    ${nfsRoot}        ${primaryIp}/24(rw,sync,no_subtree_check,no_root_squash,fsid=0,insecure)
    ${budk8sCsiRoot}  ${primaryIp}/24(rw,sync,no_subtree_check,no_root_squash,insecure)
  '';
}
