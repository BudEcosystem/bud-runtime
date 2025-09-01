output "ip" {
  description = "Public IPs nodes"

  value = {
    ingress = {
      v4 = { for ip in azurerm_public_ip.ingress_ipv4 : ip.name => ip.ip_address }
      v6 = { for ip in azurerm_public_ip.ingress_ipv6 : ip.name => ip.ip_address }
    }
    primary = {
      v4 = azurerm_public_ip.primary["IPv4"].ip_address
      v6 = azurerm_public_ip.primary["IPv6"].ip_address
    }
  }
}
