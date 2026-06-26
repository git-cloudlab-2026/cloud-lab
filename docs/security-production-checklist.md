# Checklist securite production

## Cles SSH

- Key pair officielle OpenStack : `cloud-lab-key`
- Ne pas creer de key pair par etudiant.
- Ne pas multiplier les cles de test dans le projet final.
- Cle privee locale : `secrets/cloud-lab-key`
- Cle privee jamais committee.
- La cle utilisee par Ansible doit correspondre a la key pair OpenStack `cloud-lab-key`.

## Security group

Security group officiel : `sg-student-vm`

Regles attendues :

| Direction | Protocole | Port | Source |
|-----------|-----------|------|--------|
| Entree | TCP | 22 | IP publique GIT / VPN / admin |
| Entree | TCP | 9100 | IP publique Prometheus / VPN monitoring |
| Entree | ICMP | ping | reseau interne du segment |
| Sortie | Tous | Tous | autorise |

Interdit en production :

- SSH `0.0.0.0/0`
- plusieurs security groups concurrents pour les VM etudiantes
- VM sans security group explicite

## Variables obligatoires

Dans `.env` :

```env
OPENSTACK_KEYPAIR_NAME=cloud-lab-key
OPENSTACK_SECURITY_GROUP_NAME=sg-student-vm
ANSIBLE_SSH_PRIVATE_KEY_PATH=/app/secrets/cloud-lab-key
ANSIBLE_SSH_USER=ubuntu
TERRAFORM_ALLOWED_SSH_CIDRS=["<IP_PUBLIQUE_GIT_OU_VPN>/32"]
TERRAFORM_ALLOWED_NODE_EXPORTER_CIDRS=["<IP_PUBLIQUE_PROMETHEUS_OU_VPN>/32"]
```

## Secrets hors Git

Ne jamais commit :

- `.env`
- `secrets/`
- `cloud-lab-key`
- `clouds.yaml`
- `openrc.sh`
- `terraform.tfvars`
- `*.tfstate`

Ces fichiers sont ignores par `.gitignore`.

## Verification avant demo

1. Dans Horizon, verifier que la VM utilise `cloud-lab-key`.
2. Dans Horizon, verifier que la VM utilise `sg-student-vm`.
3. Dans Horizon, verifier que SSH n'est pas ouvert a `0.0.0.0/0`.
4. Depuis le site, creer une VM.
5. Verifier dans l'audit : `vm_created`, `vm_ansible_started`, `vm_ansible_completed`.
6. Verifier Prometheus : job `cloud-lab-vm-node-exporter` avec cible `UP`.
7. Tester SSH avec la floating IP.
8. Detruire la VM depuis le site.
