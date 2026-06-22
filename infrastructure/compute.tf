resource "openstack_compute_keypair_v2" "lab_keypair" {
  name       = "cloud-lab-key"
  public_key = trimspace(file(pathexpand(var.ssh_public_key_path)))
}

resource "openstack_networking_port_v2" "lab_vm_port" {
  count          = var.vm_count
  name           = format("%s-port-%02d", var.vm_name_prefix, count.index + 1)
  network_id     = openstack_networking_network_v2.lab_network.id
  admin_state_up = true

  security_group_ids = [
    openstack_networking_secgroup_v2.lab_ssh.id
  ]

  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.lab_subnet.id
  }
}

resource "openstack_compute_instance_v2" "lab_vm" {
  count       = var.vm_count
  name        = format("%s-%02d", var.vm_name_prefix, count.index + 1)
  image_name  = var.image_name
  flavor_name = var.flavor_name
  key_pair    = openstack_compute_keypair_v2.lab_keypair.name

  network {
    port = openstack_networking_port_v2.lab_vm_port[count.index].id
  }

  depends_on = [
    openstack_networking_router_interface_v2.lab_router_interface
  ]
}

resource "openstack_networking_floatingip_v2" "lab_fip" {
  count = var.assign_floating_ip ? var.vm_count : 0
  pool  = var.external_network_name != "" ? var.external_network_name : var.external_network_id
}

resource "openstack_networking_floatingip_associate_v2" "lab_fip_assoc" {
  count       = var.assign_floating_ip ? var.vm_count : 0
  floating_ip = openstack_networking_floatingip_v2.lab_fip[count.index].address
  port_id     = openstack_networking_port_v2.lab_vm_port[count.index].id
}
