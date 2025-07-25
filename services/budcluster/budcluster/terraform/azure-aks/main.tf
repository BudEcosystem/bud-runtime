provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  subscription_id = var.subscription_id
  client_id       = var.client_id
  client_secret   = var.client_secret
  tenant_id       = var.tenant_id
}

locals {
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "Bud Ecosystem Inc."
  })
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

module "network" {
  source = "./modules/network"

  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  environment         = var.environment
  vnet_name           = "${var.environment}-vnet"
  address_space       = ["10.0.0.0/16"]
  subnet_prefixes     = ["10.0.1.0/24", "10.0.2.0/24"]
  subnet_names        = ["aks-subnet", "app-subnet"]
  tags                = local.common_tags
}

module "aks" {
  source = "./modules/aks"

  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  environment         = var.environment
  cluster_name        = "${var.environment}-bud-cluster"
  kubernetes_version  = "1.30.9"
  vnet_subnet_id      = module.network.subnet_ids["aks-subnet"]
  node_count          = 1
  vm_size             = "Standard_D2s_v3"
  tags                = local.common_tags
}
