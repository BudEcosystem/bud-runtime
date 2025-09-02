locals {
  environments = [
    "stage", # strictly follows stable git branch, this is our current prod
    "dev",   # strictly follows master git branch

    # personal dev environment
    "sinan",
    "ditto",
    "adarsh"
  ]
  # a service can be only removed if it's not required by all the environments
  # there's no need for separating them now
  services = [
    "admin",
    "customer",
    "playground",
    "gateway",
    "app",
    "ask",
    "api.novu",
    "ws.novu",
  ]
  services_with_envs = toset(flatten([
    for env in local.environments : [
      for srv in local.services :
      srv == "" ? "${env}.${var.zone_domain}" : "${srv}.${env}.${var.zone_domain}"
    ]
  ]))

  ingress_ipv4 = { for ip in toset(concat(
    [for _, ip in module.azure.ip.ingress.v4 : ip],
    [module.azure.ip.primary.v4]
  )) : ip => ip }
  ingress_ipv6 = { for ip in toset(concat(
    [for _, ip in module.azure.ip.ingress.v6 : ip],
    [module.azure.ip.primary.v6]
    )) : ip => ip
  }

  ingress_domain = "ingress.k8s.${var.zone_domain}"
}

resource "cloudflare_dns_record" "primary_ipv4" {
  zone_id = var.zone_id
  name    = "primary.k8s.${var.zone_domain}"
  ttl     = 3600
  type    = "A"
  content = module.azure.ip.primary.v4
  proxied = false
}
resource "cloudflare_dns_record" "primary_ipv6" {
  zone_id = var.zone_id
  name    = "primary.k8s.${var.zone_domain}"
  ttl     = 3600
  type    = "AAAA"
  content = module.azure.ip.primary.v6
  proxied = false
}

resource "cloudflare_dns_record" "ingress_ipv4" {
  for_each = local.ingress_ipv4
  zone_id  = var.zone_id
  name     = local.ingress_domain
  ttl      = 3600
  type     = "A"
  content  = each.key
  proxied  = false
}
resource "cloudflare_dns_record" "ingerss_ipv6" {
  for_each = local.ingress_ipv6
  zone_id  = var.zone_id
  name     = local.ingress_domain
  ttl      = 3600
  type     = "AAAA"
  content  = each.key
  proxied  = false
}
resource "cloudflare_dns_record" "services" {
  for_each = local.services_with_envs
  zone_id  = var.zone_id
  name     = each.key
  ttl      = 3600
  type     = "CNAME"
  content  = local.ingress_domain
  proxied  = false
}
