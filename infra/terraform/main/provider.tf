terraform {
  backend "s3" {
    bucket = "tfstate"
    key    = "devbox.tfstate"
    endpoints = {
      s3 = "https://s3.sinanmohd.com"
    }

    # Region validation will be skipped
    region = "us-east-1"
    # Skip AWS related checks and validations
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    # Enable path-style S3 URLs (https://<HOST>/<BUCKET> https://developer.hashicorp.com/terraform/language/settings/backends/s3#use_path_style
    use_path_style = true
  }

  required_providers {
    sops = {
      source = "carlpett/sops"
    }
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
  }
}

data "sops_file" "secrets" {
  source_file = "${path.module}/secrets.yaml"
}

provider "cloudflare" {
  api_token = data.sops_file.secrets.data["cf_token"]
}
