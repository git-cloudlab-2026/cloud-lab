resource "openstack_networking_network_v2" "lab_network" {
  name           = "cloud-lab-network"
  admin_state_up = true
}

resource "openstack_networking_subnet_v2" "lab_subnet" {
  name            = "cloud-lab-subnet"
  network_id      = openstack_networking_network_v2.lab_network.id
  cidr            = var.private_network_cidr
  ip_version      = 4
  gateway_ip      = var.private_network_gateway
  dns_nameservers = ["9.9.9.9", "1.1.1.1"]
}

resource "openstack_networking_router_v2" "lab_router" {
  name                = "cloud-lab-router"
  admin_state_up      = true
  external_network_id = var.external_network_id
}

resource "openstack_networking_router_interface_v2" "lab_router_interface" {
  router_id = openstack_networking_router_v2.lab_router.id
  subnet_id = openstack_networking_subnet_v2.lab_subnet.id
}

resource "openstack_networking_secgroup_v2" "lab_ssh" {
  name        = "cloud-lab-ssh"
  description = "Allow SSH and basic ICMP for Cloud Lab VMs."
}

resource "openstack_networking_secgroup_rule_v2" "allow_ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.allowed_ssh_cidr
  security_group_id = openstack_networking_secgroup_v2.lab_ssh.id
}

resource "openstack_networking_secgroup_rule_v2" "allow_icmp" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  remote_ip_prefix  = var.allowed_ssh_cidr
  security_group_id = openstack_networking_secgroup_v2.lab_ssh.id
}
