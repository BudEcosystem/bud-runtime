output "ip" {
  description = "Public IP of Master Node"
  value       = module.azure.master_ip
}
