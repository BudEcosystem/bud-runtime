terraform {
  required_providers {
    sops = {
      source = "carlpett/sops"
    }
    azurerm = {
      source = "hashicorp/azurerm"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}
