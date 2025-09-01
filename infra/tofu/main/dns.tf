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

  ingress_v4 = concat(
    [for _, ip in module.azure.ip.ingress.v4 : ip],
    [module.azure.ip.primary.v4]
  )
  service_with_ipv4 = {
    for tup in setproduct(local.services_with_envs, local.ingress_v4):
    "${tup[0]}=${tup[1]}" => tup
  }

  ingress_v6 = concat(
    [for _, ip in module.azure.ip.ingress.v6 : ip],
    [module.azure.ip.primary.v6]
  )
  service_with_ipv6 = {
    for tup in setproduct(local.services_with_envs, local.ingress_v6):
    "${tup[0]}=${tup[1]}" => tup
  }
}

resource "cloudflare_dns_record" "ipv4" {
  for_each = local.service_with_ipv4
  zone_id  = var.zone_id
  name     = each.value[0]
  ttl      = 3600
  type     = "A"
  content  = each.value[1]
  proxied  = false
}


resource "cloudflare_dns_record" "ipv6" {
  for_each = local.service_with_ipv6
  zone_id  = var.zone_id
  name     = each.value[0]
  ttl      = 3600
  type     = "AAAA"
  content  = each.value[1]
  proxied  = false
}
