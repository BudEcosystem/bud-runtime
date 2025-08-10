output "master_ip" {
  description = "Public IP of master node"
  value       = azurerm_public_ip.master.ip_address
}

output "worker_ips" {
  description = "Public IPs of worker nodes"
  value       = { for ip in azurerm_public_ip.worker : ip.name => ip.ip_address }
}
