resource "azurerm_network_security_group" "worker" {
  name                = "${var.prefix}-worker"
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

resource "azurerm_public_ip" "worker_ipv4" {
  for_each            = local.worker
  ip_version          = "IPv4"
  name                = "${var.prefix}-worker-${each.key}-ipv4"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_public_ip" "worker_ipv6" {
  for_each            = local.worker
  ip_version          = "IPv6"
  name                = "${var.prefix}-worker-${each.key}-ipv6"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "worker" {
  for_each            = local.worker
  name                = "${var.prefix}-worker-${each.key}"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name

  ip_configuration {
    primary                       = true
    name                          = "IPv4"
    private_ip_address_version    = "IPv4"
    subnet_id                     = azurerm_subnet.common.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.worker_ipv4[each.key].id
  }

  ip_configuration {
    primary                       = false
    name                          = "IPv6"
    private_ip_address_version    = "IPv6"
    subnet_id                     = azurerm_subnet.common.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.worker_ipv6[each.key].id
  }
}

resource "azurerm_network_interface_security_group_association" "worker" {
  for_each                  = local.worker
  network_interface_id      = azurerm_network_interface.worker[each.key].id
  network_security_group_id = azurerm_network_security_group.worker.id
}

resource "azurerm_linux_virtual_machine" "worker" {
  for_each                        = local.worker
  name                            = "${var.prefix}-worker-${each.key}"
  computer_name                   = "${var.prefix}-worker-${each.key}"
  location                        = azurerm_resource_group.common.location
  resource_group_name             = azurerm_resource_group.common.name
  network_interface_ids           = [azurerm_network_interface.worker[each.key].id]
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
    name                 = "${var.prefix}-worker-${each.key}-root"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.disk_size.worker
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}
