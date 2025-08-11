locals {
  install_user = "nixos_provisioner"
}

resource "tls_private_key" "ssh" {
  algorithm = "ED25519"
}

module "azure" {
  source = "../azure"

  prefix      = "budk8s"
  admin_user  = local.install_user
  ssh_pub_key = tls_private_key.ssh.public_key_openssh

  workers = {}
  master = {
    hostname = "master"
    disksize = 512
    sku      = "Standard_D32als_v6"
  }
}

module "nixos" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.master.config.system.build.toplevel"
}

module "disko" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.master.config.system.build.diskoScript"
}

module "install" {
  source            = "github.com/nix-community/nixos-anywhere//terraform/install"
  nixos_system      = module.nixos.result.out
  nixos_partitioner = module.disko.result.out
  instance_id       = module.azure.master_ip.v4

  target_host        = module.azure.master_ip.v4
  target_user        = local.install_user
  ssh_private_key    = tls_private_key.ssh.private_key_openssh
  extra_files_script = "${path.module}/decrypt-sops-age.sh"
}
