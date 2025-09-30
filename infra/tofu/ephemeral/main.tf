module "azure" {
  source = "../azure"

  prefix = var.environment
  primary_sku = "Standard_NC96ads_A100_v4"
  ingress_sku = {
  }
  disk_size = {
    primary      = 512
    primary_data = 1
    ingress      = 1
  }
}

resource "cloudflare_dns_record" "ipv4" {
  zone_id = var.zone.id
  name    = "${var.environment}.ephemeral.${var.zone.domain}"
  ttl     = 3600
  type    = "A"
  content = module.azure.ip.primary.v4
  proxied = false
}
resource "cloudflare_dns_record" "ipv6" {
  zone_id = var.zone.id
  name    = "${var.environment}.ephemeral.${var.zone.domain}"
  ttl     = 3600
  type    = "AAAA"
  content = module.azure.ip.primary.v6
  proxied = false
}
