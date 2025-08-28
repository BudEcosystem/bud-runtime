resource "azurerm_public_ip" "master" {
  for_each            = toset(["IPv4", "IPv6"])
  name                = "${var.prefix}-master-${lower(each.key)}"
  ip_version          = each.key
  location            = azurerm_resource_group.common.location
  resource_group_name = azurerm_resource_group.common.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "master" {
  name                           = "${var.prefix}-master"
  location                       = azurerm_resource_group.common.location
  resource_group_name            = azurerm_resource_group.common.name
  accelerated_networking_enabled = true

  ip_configuration {
    primary                       = true
    name                          = "IPv4"
    private_ip_address_version    = "IPv4"
    subnet_id                     = azurerm_subnet.master.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.master["IPv4"].id
  }

  ip_configuration {
    primary                       = false
    name                          = "IPv6"
    private_ip_address_version    = "IPv6"
    subnet_id                     = azurerm_subnet.master.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.master["IPv6"].id
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

resource "azurerm_managed_disk" "budk8s-nfs" {
  name                 = "budk8s-nfs"
  location             = azurerm_resource_group.common.location
  resource_group_name  = azurerm_resource_group.common.name
  storage_account_type = "Premium_LRS"
  create_option        = "Empty"
  disk_size_gb         = 48
}

resource "azurerm_virtual_machine_data_disk_attachment" "budk8s-nfs" {
  managed_disk_id    = azurerm_managed_disk.budk8s-nfs.id
  virtual_machine_id = azurerm_linux_virtual_machine.master.id
  lun                = "23"
  caching            = "ReadWrite"
}
