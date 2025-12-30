nixosModules:
{
  system,
  nixos-generators,
  lib,
}:
let
  imageForFormat =
    format:
    nixos-generators.nixosGenerate {
      inherit system format;

      modules = [
        ./module.nix
        nixosModules.primary
      ];
    };

  supportedFormats = [
    "amazon"
    "azure"
    "cloudstack"
    "do"
    "docker"
    "gce"
    "hyperv"
    "install-iso"
    "install-iso-hyperv"
    "iso"
    "kexec"
    "kexec-bundle"
    "kubevirt"
    "linode"
    "lxc"
    "lxc-metadata"
    "openstack"
    "proxmox"
    "proxmox-lxc"
    "qcow"
    "qcow-efi"
    "raw"
    "raw-efi"
    "sd-aarch64"
    "sd-aarch64-installer"
    "sd-x86_64"
    "vagrant-virtualbox"
    "virtualbox"
    "vm"
    "vm-bootloader"
    "vm-nogui"
    "vmware"
  ];

  attrPrefixImage = name: value: lib.attrsets.nameValuePair ("image_budk8s_" + name) value;
  images = lib.genAttrs supportedFormats imageForFormat;
in
lib.attrsets.mapAttrs' attrPrefixImage images
