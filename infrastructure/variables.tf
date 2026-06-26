variable "openstack_cloud_name" {
  description = "Nom du cloud dans clouds.yaml (section a utiliser pour l'auth OpenStack)."
  type        = string
  default     = "openstack"
}

variable "region" {
  description = "Region OpenStack Infomaniak."
  type        = string
  default     = "dc4-a"
}

variable "project_prefix" {
  description = "Prefixe applique a toutes les ressources (ex: cloud-lab)."
  type        = string
  default     = "cloud-lab"
}

variable "network_segment" {
  description = "Nom du segment reseau pedagogique (doit matcher network_segment cote backend, ex: IT-2026-A)."
  type        = string
  default     = "IT-2026-A"
}

variable "network_cidr" {
  description = "Bloc CIDR du reseau prive cree pour ce segment."
  type        = string
  default     = "10.42.0.0/24"
}

variable "external_network_name" {
  description = "Nom du reseau externe / public Infomaniak utilise pour le routeur et les floating IP."
  type        = string
  default     = "ext-floating1"
}

variable "dns_servers" {
  description = "Serveurs DNS pour le subnet prive."
  type        = list(string)
  default     = ["8.8.8.8", "1.1.1.1"]
}

variable "allowed_ssh_cidrs" {
  description = "CIDR autorises a se connecter en SSH (22) aux VM. Remplacer par l'IP publique GIT/VPN/admin en production."
  type        = list(string)
  default     = ["198.51.100.10/32"]
}

variable "allowed_node_exporter_cidrs" {
  description = "CIDR autorises a interroger node_exporter (9100) sur les VM. Remplacer par l'IP du serveur Prometheus."
  type        = list(string)
  default     = ["198.51.100.10/32"]
}

variable "image_name" {
  description = "Nom de l'image OpenStack utilisee par defaut pour les VM (ex: distribution Linux standard)."
  type        = string
  default     = "Ubuntu 24.04 LTS Noble Numbat"
}

variable "default_flavor_name" {
  description = "Flavor OpenStack par defaut (taille de VM) si aucune n'est precisee par VM."
  type        = string
  default     = "a1-ram2-disk20-perf1"
}

variable "ssh_keypair_name" {
  description = "Nom de la keypair OpenStack a utiliser/creer pour l'acces SSH aux VM."
  type        = string
  default     = "cloud-lab-key"
}

variable "ssh_public_key" {
  description = "Cle publique SSH (contenu, pas chemin) injectee dans la keypair OpenStack."
  type        = string
  sensitive   = true
}

variable "assign_floating_ip" {
  description = "Si true, attribue une floating IP publique a chaque VM provisionnee."
  type        = bool
  default     = false
}

variable "vm_requests" {
  description = <<-EOT
    Liste des VM a provisionner. Correspond au contrat attendu par le backend
    FastAPI (route /api/v1/virtual-machines/{id}/provisioning-result) :
    name, ip_address (calculee), network_segment, provider_vm_id (calcule).
  EOT
  type = list(object({
    name        = string
    flavor_name = optional(string)
    image_name  = optional(string)
    class_tag   = optional(string) # E1..E5, pour tracabilite cote audit
    owner_email = optional(string)
  }))
  default = []
}
