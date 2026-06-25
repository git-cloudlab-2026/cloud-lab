# Recupere le reseau externe Infomaniak.
data "openstack_networking_network_v2" "external" {
  name     = var.external_network_name
  external = true
}

# Recupere le reseau prive existant — utilise external=false pour filtrer.
data "openstack_networking_network_v2" "lab_network" {
  name     = "${var.project_prefix}-${var.network_segment}"
  external = false
}