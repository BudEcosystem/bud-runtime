provider "aws" {
  region     = var.region
  access_key = var.access_key
  secret_key = var.secret_key
}

locals {
  cluster_name = var.cluster_name != null ? var.cluster_name : "${var.environment}-bud-cluster"
  vpc_name     = var.vpc_name != null ? var.vpc_name : "${var.environment}-vpc"
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "Bud Ecosystem Inc."
  })
}

module "network" {
  source = "./modules/network"

  region          = var.region
  environment     = var.environment
  vpc_name        = local.vpc_name
  vpc_cidr        = "10.0.0.0/16"
  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  tags            = local.common_tags
}

module "eks" {
  source = "./modules/eks"

  region          = var.region
  environment     = var.environment
  cluster_name    = local.cluster_name
  cluster_version = "1.32"
  vpc_id          = module.network.vpc_id
  subnet_ids      = module.network.private_subnet_ids
  instance_types  = ["t3.medium"]
  desired_size    = 1
  min_size        = 1
  max_size        = 5
  tags            = local.common_tags
}

# Get available AWS availability zones
data "aws_availability_zones" "available" {
  state = "available"
}
