resource "cloudflare_dns_record" "dev" {
  for_each = toset([
    # prod required
    "admin.${var.environment}",
    "customer.${var.environment}",
    "playground.${var.environment}",
    "gateway.${var.environment}",
    "app.${var.environment}",
    "ask.${var.environment}",
    "api.novu.${var.environment}",
    "ws.novu.${var.environment}",

    # for dev only
    var.environment,
    "cloak.${var.environment}",
  ])

  zone_id = var.zone_id
  name    = each.key
  ttl     = 3600
  type    = "A"
  content = module.azure.master_ip
  proxied = false
}
