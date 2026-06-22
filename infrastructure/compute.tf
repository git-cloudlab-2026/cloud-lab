resource "openstack_compute_keypair_v2" "lab_keypair" {
  name       = "cloud-lab-key"
  public_key = file(var.ssh_public_key_path)
}

resource "openstack_compute_instance_v2" "lab_vm" {
  count       = var.vm_count
  name        = format("%s-%02d", var.vm_name_prefix, count.index + 1)
  image_name  = var.image_name
  flavor_name = var.flavor_name
  key_pair    = openstack_compute_keypair_v2.lab_keypair.name

  security_groups = [
    openstack_networking_secgroup_v2.lab_ssh.name
  ]

  network {
    uuid = openstack_networking_network_v2.lab_network.id
  }

  depends_on = [
    openstack_networking_router_interface_v2.lab_router_interface
  ]
}

resource "openstack_networking_floatingip_v2" "lab_fip" {
  count = var.assign_floating_ip ? var.vm_count : 0
  pool  = var.external_network_name != "" ? var.external_network_name : var.external_network_id
}

resource "openstack_compute_floatingip_associate_v2" "lab_fip_assoc" {
  count       = var.assign_floating_ip ? var.vm_count : 0
  floating_ip = openstack_networking_floatingip_v2.lab_fip[count.index].address
  instance_id = openstack_compute_instance_v2.lab_vm[count.index].id
}
