# Outputs structures pour matcher le payload attendu par le backend FastAPI :
# PATCH /api/v1/virtual-machines/{id}/provisioning-result
# { "provider_vm_id": ..., "ip_address": ..., "status": ..., "network_segment": ... }

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
  description = "Fingerprint de la keypair SSH utilisee pour toutes les VM du segment."
  value       = openstack_compute_keypair_v2.lab_keypair.fingerprint
}

output "network_id" {
  description = "ID du reseau prive cree pour ce segment."
  value       = openstack_networking_network_v2.lab_network.id
}

output "router_id" {
  description = "ID du routeur reliant le segment au reseau externe."
  value       = openstack_networking_router_v2.lab_router.id
}
