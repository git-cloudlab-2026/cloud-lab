resource "openstack_networking_secgroup_v2" "lab_secgroup" {
  name        = "${var.project_prefix}-${var.network_segment}-secgroup"
  description = "Isolation du segment pedagogique ${var.network_segment} - SSH entrant restreint, reste bloque par defaut"
}

# SSH entrant, restreint aux CIDR autorises (a resserrer en prod).
resource "openstack_networking_secgroup_rule_v2" "allow_ssh" {
  for_each = toset(var.allowed_ssh_cidrs)

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = each.value
  security_group_id = openstack_networking_secgroup_v2.lab_secgroup.id
}

# Metrics node_exporter entrant, limite au serveur Prometheus.
resource "openstack_networking_secgroup_rule_v2" "allow_node_exporter" {
  for_each = toset(var.allowed_node_exporter_cidrs)

  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 9100
  port_range_max    = 9100
  remote_ip_prefix  = each.value
  security_group_id = openstack_networking_secgroup_v2.lab_secgroup.id
}

# Trafic ICMP (ping) interne au segment, utile pour le diagnostic en cours.
resource "openstack_networking_secgroup_rule_v2" "allow_icmp_internal" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  remote_ip_prefix  = var.network_cidr
  security_group_id = openstack_networking_secgroup_v2.lab_secgroup.id
}


resource "openstack_compute_keypair_v2" "lab_keypair" {
  name       = var.ssh_keypair_name
  public_key = var.ssh_public_key
}
