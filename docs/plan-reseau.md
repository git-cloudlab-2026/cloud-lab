# Plan réseau — Hackathon GIT

## Architecture réseau

Chaque classe dispose d'un sous-réseau isolé sur OpenStack Infomaniak.
Les VMs d'une classe ne peuvent pas communiquer avec celles d'une autre classe.

## Sous-réseaux par classe

| Classe | Réseau | CIDR | Passerelle |
|--------|--------|------|------------|
| E1 | cloud-lab-class-e1 | 10.42.1.0/24 | 10.42.1.1 |
| Staff | cloud-lab-class-staff | 10.42.0.0/24 | 10.42.0.1 |
| IT-2026-A | cloud-lab-IT-2026-A | 10.42.0.0/24 | 10.42.0.1 |

## Règles firewall (Security Group : sg-student-vm)

| Direction | Protocole | Port | Source |
|-----------|-----------|------|--------|
| Entrée | TCP | 22 (SSH) | 0.0.0.0/0 |
| Sortie | Tous | Tous | 0.0.0.0/0 |
| Tout le reste | - | - | BLOQUÉ |

## Accès SSH

- Authentification par clé SSH uniquement
- Login root désactivé
- Mot de passe désactivé
- Maximum 3 tentatives de connexion
- Clé publique injectée dans la VM au moment du provisioning via Ansible
- Chaque étudiant reçoit sa clé privée unique

## Isolation entre classes

- Réseau séparé par classe = isolation au niveau OpenStack
- Aucune route entre les réseaux de classes différentes
- Un étudiant E1 ne peut pas atteindre une VM E2

## Intégration avec le backend

Quand une VM est approuvée et créée par Terraform (Josue) :
1. Ansible applique le rôle ssh_hardening sur la VM
2. Le backend reçoit le résultat via PATCH /api/v1/virtual-machines/{id}/provisioning-result
3. Le champ network_segment correspond au nom du réseau class-eX
