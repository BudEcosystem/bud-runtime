locals {
  private_ip_space = {
    v4 = "10.177.0.0/16"
    v6 = "fd12:babe:cafe::/48"
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
  address_space = [
    local.private_ip_space.v4,
    local.private_ip_space.v6
  ]
}

resource "azurerm_subnet" "common" {
  name                 = "${var.prefix}-common"
  resource_group_name  = azurerm_resource_group.common.name
  virtual_network_name = azurerm_virtual_network.common.name
  address_prefixes     = ["10.177.2.0/24", "fd12:babe:cafe:b00b::/64"]
}

resource "azurerm_network_security_group" "common" {
  name                = "${var.prefix}-common"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name

  security_rule {
    name                       = "${var.prefix}-inbound_ssh"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_wireguard"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Udp"
    source_port_range          = "*"
    destination_port_range     = "51820"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_mosh"
    priority                   = 300
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Udp"
    source_port_range          = "*"
    destination_port_range     = "60000-61000"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_http"
    priority                   = 400
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_https"
    priority                   = 500
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_local_ipv4"
    priority                   = 600
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = local.private_ip_space.v4
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_local_ipv6"
    priority                   = 700
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = local.private_ip_space.v6
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-outbound"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}
