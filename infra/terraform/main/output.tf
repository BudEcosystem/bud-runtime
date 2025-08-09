output "ip" {
  description = "Public IP of devbox"
  value       = module.azure.master_ip
}
