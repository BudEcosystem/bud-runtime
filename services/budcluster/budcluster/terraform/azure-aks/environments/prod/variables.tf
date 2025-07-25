variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "aks-prod-rg"
}

variable "location" {
  description = "Azure region where resources will be created"
  type        = string
  default     = "East US"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Environment = "Production"
    Owner       = "DevOps Team"
  }
}

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
  sensitive   = true
}

variable "client_id" {
  description = "Client ID of the Service Principal"
  type        = string
  sensitive   = true
}

variable "client_secret" {
  description = "Client Secret of the Service Principal"
  type        = string
  sensitive   = true
}

variable "tenant_id" {
  description = "Tenant ID of the Azure AD tenant"
  type        = string
  sensitive   = true
}
