terraform {
  backend "s3" {
    # These values must be provided via the -backend-config option with terraform init
    # bucket         = "your-terraform-state-bucket"
    # key            = "prod/terraform.tfstate"
    # region         = "us-east-1"
    # encrypt        = true
    # dynamodb_table = "terraform-lock-table"
  }
}

provider "aws" {
  region     = var.region
  access_key = var.access_key
  secret_key = var.secret_key
}

module "eks_cluster" {
  source = "../../"

  region       = var.region
  environment  = "prod"
  vpc_name     = var.vpc_name
  cluster_name = var.cluster_name
  access_key   = var.access_key
  secret_key   = var.secret_key
  tags         = var.tags
}
