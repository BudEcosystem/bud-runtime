locals {
  install_user = "nixos_provisioner"
}

resource "tls_private_key" "ssh" {
  algorithm = "ED25519"
}

module "azure" {
  source = "../azure"

  prefix = "budk8s"
  user = {
    name    = local.install_user
    ssh_key = tls_private_key.ssh.public_key_openssh
  }
  primary_sku = "Standard_D32als_v6"
  ingress_sku = {}
  worker_sku = {}
  disk_size = {
    primary      = 512
    primary_data = 4095
    ingress      = 256
    worker       = 256
  }
}

module "primary_nixos" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.primary-dev.config.system.build.toplevel"
}
module "primary_disko" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.primary-dev.config.system.build.diskoScript"
}
module "primary_install" {
  source            = "github.com/nix-community/nixos-anywhere//terraform/install"
  nixos_system      = module.primary_nixos.result.out
  nixos_partitioner = module.primary_disko.result.out
  instance_id       = module.azure.ip.primary.v4

  target_host        = module.azure.ip.primary.v4
  target_user        = local.install_user
  ssh_private_key    = tls_private_key.ssh.private_key_openssh
  extra_files_script = "${path.module}/decrypt-primary-sops-age.sh"
}

module "ingress_nixos" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.ingress.config.system.build.toplevel"
}
module "ingress_disko" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.ingress.config.system.build.diskoScript"
}
module "ingress_install" {
  for_each          = module.azure.ip.ingress.v4
  source            = "github.com/nix-community/nixos-anywhere//terraform/install"
  nixos_system      = module.ingress_nixos.result.out
  nixos_partitioner = module.ingress_disko.result.out
  instance_id       = each.value

  target_host        = each.value
  target_user        = local.install_user
  ssh_private_key    = tls_private_key.ssh.private_key_openssh
  extra_files_script = "${path.module}/decrypt-ingress-sops-age.sh"
}


module "worker_nixos" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.worker.config.system.build.toplevel"
}
module "worker_disko" {
  source    = "github.com/nix-community/nixos-anywhere//terraform/nix-build"
  attribute = ".#nixosConfigurations.worker.config.system.build.diskoScript"
}
module "worker_install" {
  for_each          = module.azure.ip.worker.v4
  source            = "github.com/nix-community/nixos-anywhere//terraform/install"
  nixos_system      = module.worker_nixos.result.out
  nixos_partitioner = module.worker_disko.result.out
  instance_id       = each.value

  target_host        = each.value
  target_user        = local.install_user
  ssh_private_key    = tls_private_key.ssh.private_key_openssh
  extra_files_script = "${path.module}/decrypt-worker-sops-age.sh"
}
