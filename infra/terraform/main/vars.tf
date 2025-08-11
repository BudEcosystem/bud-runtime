variable "environment" {
  default = "dev"
}

variable "zone_id" {
  default = "1f83390b02ecdecfb95d3964721d9fcb" # bud.studio
}

# just zone_id is needed, this is to work around a provider bug,
# avoid changes on every apply eg: admin.dev.bud.studio -> admin.dev
variable "zone_domain" {
  default = "bud.studio" # bud.studio
}
