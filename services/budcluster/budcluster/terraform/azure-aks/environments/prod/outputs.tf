output "resource_group_name" {
  description = "Name of the resource group"
  value       = module.aks_cluster.resource_group_name
}

output "aks_cluster_name" {
  description = "Name of the AKS cluster"
  value       = module.aks_cluster.aks_cluster_name
}

output "aks_cluster_id" {
  description = "ID of the AKS cluster"
  value       = module.aks_cluster.aks_cluster_id
}

output "kube_config" {
  description = "Kubernetes configuration"
  value       = module.aks_cluster.kube_config
  sensitive   = true
}

output "aks_host" {
  description = "AKS cluster host"
  value       = module.aks_cluster.aks_host
  sensitive   = true
}

output "vnet_name" {
  description = "Name of the Virtual Network"
  value       = module.aks_cluster.vnet_name
}

output "subnet_ids" {
  description = "Map of subnet names to IDs"
  value       = module.aks_cluster.subnet_ids
}
