output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks_cluster.cluster_name
}

output "cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = module.eks_cluster.cluster_arn
}

output "aks_host" {
  description = "Endpoint for the EKS cluster"
  value       = module.eks_cluster.aks_host
  sensitive   = true
}

output "kube_config" {
  description = "Kubernetes configuration"
  value       = module.eks_cluster.kube_config
  sensitive   = true
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.eks_cluster.vpc_id
}

output "vpc_name" {
  description = "Name of the VPC"
  value       = module.eks_cluster.vpc_name
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.eks_cluster.private_subnet_ids
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.eks_cluster.public_subnet_ids
}
