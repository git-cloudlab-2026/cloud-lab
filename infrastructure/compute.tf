data "openstack_images_image_v2" "vm_image" {
  for_each = { for v in var.vm_requests : v.name => v }

name        = coalesce(each.value.image_name, var.image_name)
  most_recent = true
}

resource "openstack_compute_instance_v2" "vm" {
  for_each = { for v in var.vm_requests : v.name => v }

  name        = "${var.project_prefix}-${each.value.name}"
  flavor_name = coalesce(each.value.flavor_name, var.default_flavor_name)
  image_id    = data.openstack_images_image_v2.vm_image[each.key].id
  key_pair    = openstack_compute_keypair_v2.lab_keypair.name
  region      = var.region

  security_groups = [openstack_networking_secgroup_v2.lab_secgroup.name]

  network {
    uuid = openstack_networking_network_v2.lab_network.id
  }

  metadata = {
    cloud_lab_segment = var.network_segment
    cloud_lab_class   = coalesce(each.value.class_tag, "n/a")
    cloud_lab_owner   = coalesce(each.value.owner_email, "n/a")
  }

  depends_on = [openstack_networking_router_interface_v2.lab_router_interface]
}

resource "openstack_networking_floatingip_v2" "vm_fip" {
  for_each = var.assign_floating_ip ? openstack_compute_instance_v2.vm : {}

  pool = var.external_network_name
}

resource "openstack_compute_floatingip_associate_v2" "vm_fip_assoc" {
  for_each = var.assign_floating_ip ? openstack_compute_instance_v2.vm : {}

  floating_ip = openstack_networking_floatingip_v2.vm_fip[each.key].address
  instance_id = each.value.id
}
