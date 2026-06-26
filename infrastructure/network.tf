data "openstack_networking_network_v2" "external" {
  name = var.external_network_name
}

resource "openstack_networking_network_v2" "lab_network" {
  name           = "${var.project_prefix}-${var.network_segment}"
  admin_state_up = true

  tags = [
    "cloud-lab",
    var.network_segment,
  ]
}

resource "openstack_networking_subnet_v2" "lab_subnet" {
  name            = "${var.project_prefix}-${var.network_segment}-subnet"
  network_id      = openstack_networking_network_v2.lab_network.id
  cidr            = var.network_cidr
  ip_version      = 4
  dns_nameservers = var.dns_servers

  tags = [
    "cloud-lab",
    var.network_segment,
  ]
}

resource "openstack_networking_router_v2" "lab_router" {
  name                = "${var.project_prefix}-${var.network_segment}-router"
  admin_state_up      = true
  external_network_id = data.openstack_networking_network_v2.external.id
}

resource "openstack_networking_router_interface_v2" "lab_router_interface" {
  router_id = openstack_networking_router_v2.lab_router.id
  subnet_id = openstack_networking_subnet_v2.lab_subnet.id
}
