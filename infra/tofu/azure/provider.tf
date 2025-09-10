terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
    sops = {
      source = "carlpett/sops"
    }
  }
}

data "sops_file" "secrets" {
  source_file = "${path.module}/secrets.yaml"
}

provider "azurerm" {
  features {}

  client_id       = data.sops_file.secrets.data["azure.appId"]
  client_secret   = data.sops_file.secrets.data["azure.password"]
  tenant_id       = data.sops_file.secrets.data["azure.tenant"]
  subscription_id = data.sops_file.secrets.data["azure.subscription_id"]
}
