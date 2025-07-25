terraform {
  backend "s3" {}
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

module "aks_cluster" {
  source = "../../"

  subscription_id     = var.subscription_id
  client_id           = var.client_id
  client_secret       = var.client_secret
  tenant_id           = var.tenant_id
  resource_group_name = var.resource_group_name
  location            = var.location
  environment         = "prod"
  tags                = var.tags

}
