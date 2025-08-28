# in budk8s primary hosts the nfs storage using NixOS modules, and runs wireguard & scid,

resource "azurerm_public_ip" "primary" {
  for_each            = toset(["IPv4", "IPv6"])
  name                = "${var.prefix}-primary-${lower(each.key)}"
  ip_version          = each.key
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "primary" {
  name                           = "${var.prefix}-primary"
  location                       = azurerm_resource_group.common.location
  resource_group_name            = azurerm_resource_group.common.name
  accelerated_networking_enabled = true

  ip_configuration {
    primary                       = true
    name                          = "IPv4"
    private_ip_address_version    = "IPv4"
    subnet_id                     = azurerm_subnet.common.id
    private_ip_address_allocation = "Static"
    private_ip_address            = "10.177.2.69"
    public_ip_address_id          = azurerm_public_ip.primary["IPv4"].id
  }

  ip_configuration {
    primary                       = false
    name                          = "IPv6"
    private_ip_address_version    = "IPv6"
    subnet_id                     = azurerm_subnet.common.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.primary["IPv6"].id
  }
}

resource "azurerm_network_interface_security_group_association" "primary" {
  network_interface_id      = azurerm_network_interface.primary.id
  network_security_group_id = azurerm_network_security_group.common.id
}

resource "azurerm_linux_virtual_machine" "primary" {
  name                            = "${var.prefix}-primary"
  computer_name                   = "${var.prefix}-primary"
  location                        = azurerm_resource_group.common.location
  resource_group_name             = azurerm_resource_group.common.name
  network_interface_ids           = [azurerm_network_interface.primary.id]
  size                            = var.primary_sku
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
    name                 = "${var.prefix}-primary-root"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.disk_size.primary
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}

resource "azurerm_managed_disk" "primary-data" {
  name                 = "primary-data"
  location             = azurerm_resource_group.common.location
  resource_group_name  = azurerm_resource_group.common.name
  storage_account_type = "Premium_LRS"
  create_option        = "Empty"
  disk_size_gb         = var.disk_size.primary_data
}

resource "azurerm_virtual_machine_data_disk_attachment" "primary-data" {
  managed_disk_id    = azurerm_managed_disk.primary-data.id
  virtual_machine_id = azurerm_linux_virtual_machine.primary.id
  lun                = "23"
  caching            = "ReadWrite"
}
