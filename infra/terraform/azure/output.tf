output "primary_ip" {
  description = "Public IP of Primary node"
  value = {
    v4 = azurerm_public_ip.primary["IPv4"].ip_address
    v6 = azurerm_public_ip.primary["IPv6"].ip_address
  }
}

output "ingress_ips" {
  description = "Public IPs of Ingress nodes"
  value = {
    v4 = { for ip in azurerm_public_ip.ingress_ipv4 : ip.name => ip.ip_address }
    v6 = { for ip in azurerm_public_ip.ingress_ipv6 : ip.name => ip.ip_address }
  }
}
