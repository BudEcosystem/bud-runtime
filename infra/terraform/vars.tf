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
  default = "dev-terraform"
}

variable "admin_user" {
  default = "bud"
}

variable "admin_password" {
  default = "Bud@11"
}

variable "ssh_pub_key" {
  default = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIL8LnyOuPmtKRqAZeHueNN4kfYvpRQVwCivSTq+SZvDU sinan@cez"
}

variable "subscription_id" {
  default = "9a518351-b5cc-40cb-932b-f3e512818658"
}

variable "workers" {
  type        = map(string)
  description = "Map of worker sku to sku count"

  default = {
    Standard_NC24ads_A100_v4   = 0 // NVIDIA A100
    Standard_NV12ads_A10_v5    = 0 // NVIDIA A10
    Standard_DS1_v2            = 0 // CPU
    Standard_ND96isr_MI300X_v5 = 2 // AMD MI300
  }
}
