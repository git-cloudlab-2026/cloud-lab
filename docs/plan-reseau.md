# Plan reseau - Hackathon GIT

## Architecture reseau

Chaque classe dispose d'un sous-reseau isole sur OpenStack Infomaniak.
Les VMs d'une classe ne doivent pas communiquer avec celles d'une autre classe.

## Sous-reseaux par classe

| Classe | Reseau | CIDR | Passerelle |
|--------|--------|------|------------|
| E1 | class-e1 | 10.10.1.0/24 | 10.10.1.1 |
| E2 | class-e2 | 10.10.2.0/24 | 10.10.2.1 |
| E3 | class-e3 | 10.10.3.0/24 | 10.10.3.1 |
| Staff/Formateurs | class-staff | 10.10.0.0/24 | 10.10.0.1 |

## Regles firewall

Security group officiel : `sg-student-vm`

| Direction | Protocole | Port | Source |
|-----------|-----------|------|--------|
| Entree | TCP | 22 (SSH) | IP publique GIT / VPN / admin uniquement |
| Entree | ICMP | ping | Reseau interne du segment |
| Sortie | Tous | Tous | Autorise |
| Tout le reste | - | - | Bloque |

Important : `0.0.0.0/0` est acceptable uniquement pour une demo temporaire. Il ne doit pas rester en configuration finale.

## Acces SSH

- Une seule paire de cles officielle OpenStack : `cloud-lab-key`
- Cle privee hors Git : `secrets/cloud-lab-key`
- Authentification par cle SSH uniquement
- Login root desactive
- Mot de passe desactive
- Maximum 3 tentatives de connexion
- Ansible reutilise `cloud-lab-key` pour configurer les VM apres creation

## Isolation entre classes

- Reseau separe par classe = isolation au niveau OpenStack
- Aucune route entre les reseaux de classes differentes
- Un etudiant E1 ne doit pas atteindre une VM E2

## Integration backend

Quand une demande VM est approuvee :

1. Le backend cree la VM sur OpenStack Infomaniak.
2. La VM utilise la key pair `cloud-lab-key`.
3. La VM est attachee au security group `sg-student-vm`.
4. Ansible configure la VM via SSH.
5. Le journal d'audit garde la trace de creation, configuration et destruction.
