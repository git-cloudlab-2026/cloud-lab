terraform {
  required_version = ">= 1.6.0"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.53"
    }
  }
}

provider "openstack" {
  # Authentification via clouds.yaml (recommande, pas de secret dans le code).
  # ~/.config/openstack/clouds.yaml ou ./clouds.yaml a la racine du module.
  cloud = var.openstack_cloud_name
}
