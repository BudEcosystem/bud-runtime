resource "azurerm_subnet" "master" {
  name                 = "${var.prefix}-master"
  resource_group_name  = azurerm_resource_group.common.name
  virtual_network_name = azurerm_virtual_network.common.name
  address_prefixes     = ["10.177.2.0/24"]
}

resource "azurerm_public_ip" "master" {
  name                = "${var.prefix}-master"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_network_security_group" "master" {
  name                = "${var.prefix}-master"
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name

  # pass through, firewall managed by NixOS
  security_rule {
    name                       = "${var.prefix}-inbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
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

resource "azurerm_network_interface" "master" {
  name                           = "${var.prefix}-master"
  location                       = azurerm_resource_group.common.location
  resource_group_name            = azurerm_resource_group.common.name
  accelerated_networking_enabled = true

  ip_configuration {
    name                          = "master"
    subnet_id                     = azurerm_subnet.master.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.master.id
  }
}

resource "azurerm_network_interface_security_group_association" "master" {
  network_interface_id      = azurerm_network_interface.master.id
  network_security_group_id = azurerm_network_security_group.master.id
}

resource "azurerm_linux_virtual_machine" "master" {
  name                            = "${var.prefix}-master"
  computer_name                   = var.master.hostname
  location                        = azurerm_resource_group.common.location
  resource_group_name             = azurerm_resource_group.common.name
  network_interface_ids           = [azurerm_network_interface.master.id]
  size                            = var.master.sku
  secure_boot_enabled             = false
  vtpm_enabled                    = false
  disable_password_authentication = true
  admin_username                  = var.admin_user

  boot_diagnostics {
    storage_account_uri = null
  }

  admin_ssh_key {
    username   = var.admin_user
    public_key = var.ssh_pub_key
  }

  os_disk {
    name                 = "${var.prefix}-master-root"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.master.disksize
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}
