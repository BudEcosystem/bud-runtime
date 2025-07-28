resource "azurerm_subnet" "worker" {
  name                 = "${var.prefix}-worker"
  resource_group_name  = azurerm_resource_group.common.name
  virtual_network_name = azurerm_virtual_network.common.name
  address_prefixes     = ["10.177.3.0/24"]
}

resource "azurerm_public_ip" "worker" {
  for_each            = local.workers
  name                = "${var.prefix}-worker-${each.key}"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_network_security_group" "worker" {
  name                = "${var.prefix}-worker"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name

  security_rule {
    name                       = "${var.prefix}-worker_inbound_ssh"
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
    name                       = "${var.prefix}-worker_inbound_local"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = one(azurerm_virtual_network.common.address_space)
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "${var.prefix}-worker_outbound"
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

resource "azurerm_network_interface" "worker" {
  for_each            = local.workers
  name                = "${var.prefix}-worker-${each.key}"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name

  ip_configuration {
    name                          = "worker"
    subnet_id                     = azurerm_subnet.worker.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.worker[each.key].id
  }
}

resource "azurerm_network_interface_security_group_association" "worker" {
  for_each                  = local.workers
  network_interface_id      = azurerm_network_interface.worker[each.key].id
  network_security_group_id = azurerm_network_security_group.worker.id
}

resource "azurerm_linux_virtual_machine" "worker" {
  for_each                        = local.workers
  name                            = "${var.prefix}-worker-${each.key}"
  computer_name                   = "${var.prefix}-worker-${each.key}"
  location                        = azurerm_resource_group.common.location
  resource_group_name             = azurerm_resource_group.common.name
  network_interface_ids           = [azurerm_network_interface.worker[each.key].id]
  size                            = each.value
  secure_boot_enabled             = false
  vtpm_enabled                    = false
  disable_password_authentication = true
  admin_username                  = var.admin_user

  admin_ssh_key {
    username   = var.admin_user
    public_key = var.ssh_pub_key
  }

  os_disk {
    name                 = "${var.prefix}-worker-${each.key}-root"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 128
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}
