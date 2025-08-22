locals {
  environments = [
    "stage", # strictly follows stable git branch, this is our current prod
    "dev",   # strictly follows master git branch

    # personal dev environment
    "sinan",
    "ditto",
    "varun",
    "adarsh"
  ]

  # a service can be only removed if it's not required by all the environments
  # there's no need for separating them now
  services = [
    # bud stack requirement
    "admin",
    "customer",
    "playground",
    "gateway",
    "app",
    "ask",
    "api.novu",
    "ws.novu",

    # for development only
    "",
    "cloak",
  ]

  services_with_envs = toset(flatten([
    for env in local.environments : [
      for srv in local.services :
      srv == "" ? "${env}.${var.zone_domain}" : "${srv}.${env}.${var.zone_domain}"
    ]
  ]))
}

resource "cloudflare_dns_record" "ipv4" {
  for_each = local.services_with_envs
  zone_id  = var.zone_id
  name     = each.key
  ttl      = 3600
  type     = "A"
  content  = module.azure.master_ip.v4
  proxied  = false
}


resource "cloudflare_dns_record" "ipv6" {
  for_each = local.services_with_envs
  zone_id  = var.zone_id
  name     = each.key
  ttl      = 3600
  type     = "AAAA"
  content  = module.azure.master_ip.v6
  proxied  = false
}
