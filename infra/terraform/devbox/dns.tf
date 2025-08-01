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

resource "cloudflare_dns_record" "admin" {
  zone_id = local.zone_id
  name = "admin.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}

resource "cloudflare_dns_record" "playground" {
  zone_id = local.zone_id
  name = "playground.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}

resource "cloudflare_dns_record" "app" {
  zone_id = local.zone_id
  name = "app.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}

resource "cloudflare_dns_record" "ask" {
  zone_id = local.zone_id
  name = "ask.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}

resource "cloudflare_dns_record" "gateway" {
  zone_id = local.zone_id
  name = "gateway.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}

resource "cloudflare_dns_record" "novu_ws" {
  zone_id = local.zone_id
  name = "ws.novu.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}

resource "cloudflare_dns_record" "novu_api" {
  zone_id = local.zone_id
  name = "api.novu.dev"
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}
