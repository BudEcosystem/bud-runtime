resource "azurerm_resource_group" "common" {
  name     = var.prefix
  location = "West US"
}

resource "azurerm_virtual_network" "common" {
  name                = var.prefix
  resource_group_name = azurerm_resource_group.common.name
  location            = azurerm_resource_group.common.location
  address_space       = ["10.177.0.0/16"]
}
