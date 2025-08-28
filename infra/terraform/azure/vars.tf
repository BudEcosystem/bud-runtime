locals {
  # hostname => sku
  ingress = merge(
    flatten([
      for sku, count in var.ingress_sku : [for i in range(count) : {
        "${replace(sku, "/[^a-zA-Z0-9]/", "")}-${i}" = sku
      }]]
    )...
  )
}

variable "prefix" {
  type        = string
  description = "Name to prefix cloud resources"
  default     = "tofu"
}

variable "disk_size" {
  description = "Disk size assosiated with vms"
  # in GB
  default = {
    primary      = 64
    primary_data = 128
    ingress      = 32
  }
}

variable "user" {
  type        = map(string)
  description = "User information"

  default = {
    name    = "bud"
    ssh_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIL8LnyOuPmtKRqAZeHueNN4kfYvpRQVwCivSTq+SZvDU sinan@cez"
  }
}

variable "primary_sku" {
  type        = string
  description = "Sku for the primary vm"
  default     = "Standard_DS1_v2"
}

variable "ingress_sku" {
  type        = map(string)
  description = "Map of ingress sku to sku count"

  default = {
    Standard_DS1_v2            = 1 // CPU
    Standard_NC24ads_A100_v4   = 0 // NVIDIA A100
    Standard_NV12ads_A10_v5    = 0 // NVIDIA A10
    Standard_ND96isr_MI300X_v5 = 0 // AMD MI300
  }
}
