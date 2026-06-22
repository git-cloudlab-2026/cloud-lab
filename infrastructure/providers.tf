terraform {
  required_version = ">= 1.5.0"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53"
    }
  }
}

provider "openstack" {
  auth_url    = var.auth_url
  region      = var.region
  tenant_name = var.project_name
  user_name   = var.username
  password    = var.password
}
