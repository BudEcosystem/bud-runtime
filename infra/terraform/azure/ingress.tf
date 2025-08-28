resource "azurerm_subnet" "ingress" {
  name                 = "${var.prefix}-ingress"
  resource_group_name  = azurerm_resource_group.common.name
  virtual_network_name = azurerm_virtual_network.common.name
  address_prefixes     = ["10.177.2.0/24", "fd12:babe:cafe::/48"]
}

resource "azurerm_network_security_group" "ingress" {
  name                = "${var.prefix}-ingress"
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
    priority                   = 100
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
    priority                   = 100
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
    priority                   = 80
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_https"
    priority                   = 443
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-inbound_local_ipv4"
    priority                   = 150
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
    priority                   = 200
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
