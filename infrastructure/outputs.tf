output "network_id" {
  description = "Private OpenStack network ID."
  value       = openstack_networking_network_v2.lab_network.id
}

output "subnet_id" {
  description = "Private OpenStack subnet ID."
  value       = openstack_networking_subnet_v2.lab_subnet.id
}

output "router_id" {
  description = "OpenStack router ID."
  value       = openstack_networking_router_v2.lab_router.id
}

output "security_group_id" {
  description = "Security group allowing SSH access."
  value       = openstack_networking_secgroup_v2.lab_ssh.id
}

output "vm_ids" {
  description = "Created VM IDs."
  value       = openstack_compute_instance_v2.lab_vm[*].id
}

output "vm_names" {
  description = "Created VM names."
  value       = openstack_compute_instance_v2.lab_vm[*].name
}

output "private_ips" {
  description = "Private fixed IPs."
  value       = [for port in openstack_networking_port_v2.lab_vm_port : port.all_fixed_ips[0]]
}

output "floating_ips" {
  description = "Public floating IPs when enabled."
  value       = var.assign_floating_ip ? openstack_networking_floatingip_v2.lab_fip[*].address : []
}

output "ssh_commands" {
  description = "Ready-to-use SSH commands."
  value = [
    for ip in(var.assign_floating_ip ? openstack_networking_floatingip_v2.lab_fip[*].address : [for port in openstack_networking_port_v2.lab_vm_port : port.all_fixed_ips[0]]) :
    "ssh ubuntu@${ip}"
  ]
}
