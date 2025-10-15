output "ip" {
  value = module.azure.ip
}

output "dns" {
  value = cloudflare_dns_record.ipv4.name
}
