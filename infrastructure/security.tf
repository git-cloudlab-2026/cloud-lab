# Recupere le security group existant — ne le recrée pas.
# Le security group est une ressource partagée créée une seule fois
# par l'infrastructure de base (terraform apply sur l'infra commune).
data "openstack_networking_secgroup_v2" "lab_secgroup" {
  name = "${var.project_prefix}-${var.network_segment}-secgroup"
}
