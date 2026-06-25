output "provisioning_results" {
  description = "Resultats de provisioning, un objet par VM, prets a etre envoyes au backend."
  value = {
    for name, vm in openstack_compute_instance_v2.vm : name => {
      provider_vm_id  = vm.id
      ip_address      = var.assign_floating_ip ? openstack_networking_floatingip_v2.vm_fip[name].address : vm.access_ip_v4
      status          = "running"
      network_segment = var.network_segment
    }
  }
}

output "ssh_fingerprint" {
  description = "Nom de la keypair SSH OpenStack reutilisee pour toutes les VM."
  value       = var.ssh_keypair_name
}
