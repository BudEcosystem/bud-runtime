locals {
  # bud.studio
  zone_id = "1f83390b02ecdecfb95d3964721d9fcb"
}

resource "cloudflare_dns_record" "dev" {
  for_each = toset([
    "dev",
    "argo.dev",
    "admin.dev",
    "playground.dev",
    "gateway.dev",
    "app.dev",
    "ask.dev",
    "api.novu.dev",
    "ws.novu.dev",
  ])

  zone_id = local.zone_id
  name = each.key
  ttl = 3600
  type = "A"
  content = module.azure.master_ip
  proxied = false
}
