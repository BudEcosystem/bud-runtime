locals {
  # bud.studio
  zone_id = "1f83390b02ecdecfb95d3964721d9fcb"
}

resource "cloudflare_dns_record" "master" {
  zone_id = local.zone_id
  name = "dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}


resource "cloudflare_dns_record" "argo" {
  zone_id = local.zone_id
  name = "argo.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}
