locals {
  private_ip_space = {
    v4 = "10.177.0.0/16"
    v6 = "fd12:3456:789a::/48"
  }
}

resource "azurerm_resource_group" "common" {
  name     = var.prefix
  location = "West US"
}

resource "azurerm_virtual_network" "common" {
  name                = var.prefix
  resource_group_name = azurerm_resource_group.common.name
  location            = azurerm_resource_group.common.location
  address_space       = [
    local.private_ip_space.v4,
    local.private_ip_space.v6
  ]
}
