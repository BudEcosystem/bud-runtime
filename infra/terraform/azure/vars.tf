locals {
  # hostname => sku
  workers = merge(
    flatten([
      for sku, count in var.workers : [for i in range(count) : {
        "${replace(sku, "/[^a-zA-Z0-9]/", "")}-${i}" = sku
      }]]
    )...
  )
}

variable "prefix" {
  default = "terraform"
}

variable "master" {
  default = {
    hostname = "master"
    disksize = 128
    sku      = "Standard_DS1_v2"
  }
}

variable "admin_user" {
  default = "bud"
}

variable "ssh_pub_key" {
  default = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIL8LnyOuPmtKRqAZeHueNN4kfYvpRQVwCivSTq+SZvDU sinan@cez"
}

variable "workers" {
  type        = map(string)
  description = "Map of worker sku to sku count"

  default = {
    Standard_NC24ads_A100_v4   = 0 // NVIDIA A100
    Standard_NV12ads_A10_v5    = 0 // NVIDIA A10
    Standard_DS1_v2            = 0 // CPU
    Standard_ND96isr_MI300X_v5 = 0 // AMD MI300
  }
}
