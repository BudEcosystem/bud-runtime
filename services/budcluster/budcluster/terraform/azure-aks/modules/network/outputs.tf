output "vnet_id" {
  description = "ID of the virtual network"
  value       = azurerm_virtual_network.this.id
}

output "vnet_name" {
  description = "Name of the virtual network"
  value       = azurerm_virtual_network.this.name
}

output "subnet_ids" {
  description = "Map of subnet names to IDs"
  value       = { for i, subnet in azurerm_subnet.this : var.subnet_names[i] => subnet.id }
}

output "aks_subnet_id" {
  description = "ID of the AKS subnet"
  value       = azurerm_subnet.this[index(var.subnet_names, "aks-subnet")].id
}

output "nsg_id" {
  description = "ID of the AKS network security group"
  value       = azurerm_network_security_group.aks.id
}

output "route_table_id" {
  description = "ID of the AKS route table"
  value       = azurerm_route_table.aks.id
} 