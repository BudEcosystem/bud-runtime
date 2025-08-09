output "master_ip" {
  description = "Public IP of master node"
  value       = {
    v4 = azurerm_public_ip.master["IPv4"].ip_address
    v6 = azurerm_public_ip.master["IPv6"].ip_address
  }
}

output "worker_ips" {
  description = "Public IPs of worker nodes"
  value       = {
    v4 = { for ip in azurerm_public_ip.worker_ipv4 : ip.name => ip.ip_address }
    v6 = { for ip in azurerm_public_ip.worker_ipv6 : ip.name => ip.ip_address }
  }
}
