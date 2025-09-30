variable "environment" {
  default = "stove8s"
}

variable "zone" {
  default = {
    id = "1f83390b02ecdecfb95d3964721d9fcb" # bud.studio
    # just id is needed, this is to work around a provider bug,
    # avoid changes on every apply eg: admin.dev.bud.studio -> admin.dev
    domain = "bud.studio"
  }
}
