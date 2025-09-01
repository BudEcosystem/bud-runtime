resource "azurerm_public_ip" "ingress_ipv4" {
  for_each            = local.ingress
  ip_version          = "IPv4"
  name                = "${var.prefix}-ingress-${each.key}-ipv4"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_public_ip" "ingress_ipv6" {
  for_each            = local.ingress
  ip_version          = "IPv6"
  name                = "${var.prefix}-ingress-${each.key}-ipv6"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "ingress" {
  for_each            = local.ingress
  name                = "${var.prefix}-ingress-${each.key}"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name

  ip_configuration {
    primary                       = true
    name                          = "IPv4"
    private_ip_address_version    = "IPv4"
    subnet_id                     = azurerm_subnet.common.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.ingress_ipv4[each.key].id
  }

  ip_configuration {
    primary                       = false
    name                          = "IPv6"
    private_ip_address_version    = "IPv6"
    subnet_id                     = azurerm_subnet.common.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.ingress_ipv6[each.key].id
  }
}

resource "azurerm_network_interface_security_group_association" "ingress" {
  for_each                  = local.ingress
  network_interface_id      = azurerm_network_interface.ingress[each.key].id
  network_security_group_id = azurerm_network_security_group.common.id
}

resource "azurerm_linux_virtual_machine" "ingress" {
  for_each                        = local.ingress
  name                            = "${var.prefix}-ingress-${each.key}"
  computer_name                   = "${var.prefix}-ingress-${each.key}"
  location                        = azurerm_resource_group.common.location
  resource_group_name             = azurerm_resource_group.common.name
  network_interface_ids           = [azurerm_network_interface.ingress[each.key].id]
  size                            = each.value
  secure_boot_enabled             = false
  vtpm_enabled                    = false
  disable_password_authentication = true
  admin_username                  = var.user.name

  boot_diagnostics {
    storage_account_uri = null
  }

  admin_ssh_key {
    username   = var.user.name
    public_key = var.user.ssh_key
  }

  os_disk {
    name                 = "${var.prefix}-ingress-${each.key}-root"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.disk_size.ingress
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}
