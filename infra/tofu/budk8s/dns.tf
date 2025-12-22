locals {
  environments = [
    "stage", # strictly follows stable git branch, this is our current prod
    "dev",   # strictly follows master git branch
  ]

  # personal dev environment
  environments_pde = [
    "sinan",
    "ditto",
    "adarsh",
    "varun",
    "karthik"
  ]

  # a service can be only removed if it's not required by all the environments
  services = [
    "s3",
    "admin",
    "customer",
    "playground",
    "gateway",
    "app",
    "ask",
    "mcpgateway",
    "api.novu",
    "ws.novu",
    "chat",
  ]

  # place holder domains for new pde services
  # that are not yet merged upstream
  services_pde = [
    "temp",
  ]

  services_standalone = [
    "harbor",
    "connect.dev"
  ]

  services_with_envs = toset(concat(
    flatten([
      for env in local.environments : [
        for srv in local.services :
        srv == "" ? "${env}.${var.zone.domain}" : "${srv}.${env}.${var.zone.domain}"
      ]
    ])
    ,
    flatten([
      for env in local.environments_pde : [
        for srv in concat(local.services_pde, local.services) :
        srv == "" ? "${env}.${var.zone.domain}" : "${srv}.${env}.${var.zone.domain}"
      ]
    ]),
    flatten([
      for srv in local.services_standalone : [
        "${srv}.${var.zone.domain}"
      ]
    ]),
  ))
  ingress_ipv4 = { for ip in toset(concat(
    [for _, ip in module.azure.ip.ingress.v4 : ip],
    [module.azure.ip.primary.v4]
  )) : ip => ip }
  ingress_ipv6 = { for ip in toset(concat(
    [for _, ip in module.azure.ip.ingress.v6 : ip],
    [module.azure.ip.primary.v6]
    )) : ip => ip
  }

  ingress_domain = "ingress.k8s.${var.zone.domain}"
}

resource "cloudflare_dns_record" "primary_ipv4" {
  zone_id = var.zone.id
  name    = "primary.k8s.${var.zone.domain}"
  ttl     = 3600
  type    = "A"
  content = module.azure.ip.primary.v4
  proxied = false
}
resource "cloudflare_dns_record" "primary_ipv6" {
  zone_id = var.zone.id
  name    = "primary.k8s.${var.zone.domain}"
  ttl     = 3600
  type    = "AAAA"
  content = module.azure.ip.primary.v6
  proxied = false
}

resource "cloudflare_dns_record" "ingress_ipv4" {
  for_each = local.ingress_ipv4
  zone_id  = var.zone.id
  name     = local.ingress_domain
  ttl      = 3600
  type     = "A"
  content  = each.key
  proxied  = false
}
resource "cloudflare_dns_record" "ingerss_ipv6" {
  for_each = local.ingress_ipv6
  zone_id  = var.zone.id
  name     = local.ingress_domain
  ttl      = 3600
  type     = "AAAA"
  content  = each.key
  proxied  = false
}
resource "cloudflare_dns_record" "services" {
  for_each = local.services_with_envs
  zone_id  = var.zone.id
  name     = each.key
  ttl      = 3600
  type     = "CNAME"
  content  = local.ingress_domain
  proxied  = false
}
