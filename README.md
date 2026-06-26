# Cloud Lab Control Center

Plateforme de pilotage d'environnements pedagogiques sur Infomaniak Public Cloud.

Cloud Lab permet de demander, valider, provisionner, configurer, superviser et detruire automatiquement des machines virtuelles temporaires pour les cours du Geneva Institute of Technology.

```text
Demande -> Validation -> Terraform -> OpenStack -> Ansible -> Monitoring -> Fin de vie
```

## Objectif

Le projet repond a un besoin simple : fournir des VMs de cours sans gestion manuelle permanente.

Un etudiant ou un enseignant cree une demande depuis le portail. Un validateur l'approuve. Le backend lance le provisioning OpenStack via Terraform, configure la VM avec Ansible, expose les metriques a Prometheus/Grafana, suit les couts et detruit la VM a sa date de fin.

## Fonctionnalites

- portail web de demandes de VMs;
- roles applicatifs : student, teacher, validator, admin;
- workflow complet : demande, approbation, refus, provisioning, configuration, destruction;
- backend FastAPI avec API versionnee `/api/v1`;
- base PostgreSQL avec SQLAlchemy et Alembic;
- provisioning reel sur Infomaniak OpenStack via Terraform;
- configuration post-provisioning via Ansible;
- installation automatique des outils par template;
- installation de `prometheus-node-exporter` sur les VMs;
- monitoring Prometheus/Grafana;
- journal d'audit complet;
- notifications applicatives;
- modele de cout interne par flavor et duree;
- scheduler de fin de vie;
- mode mock pour developpement local sans consommer de ressources cloud;
- documentation OpenAPI automatique.

## Architecture

```mermaid
flowchart LR
  U["Utilisateur GIT"] --> F["Frontend web"]
  F --> A["Backend FastAPI"]
  A --> DB["PostgreSQL"]
  A --> AUTH["Auth mock / OIDC Entra ID"]
  A --> TF["Terraform service"]
  TF --> OS["Infomaniak OpenStack"]
  OS --> VM["VM Ubuntu 24.04"]
  A --> AN["Ansible service"]
  AN --> VM
  VM --> NE["node_exporter"]
  P["Prometheus"] --> NE
  G["Grafana"] --> P
  A --> SCH["Scheduler lifecycle"]
```

## Structure

```text
app/                         Frontend HTML/CSS/JS
server/                      Backend FastAPI
server/alembic/              Migrations base de donnees
server/app/services/         Services metier
infrastructure/              Terraform Infomaniak OpenStack
ansible/                     Playbooks et roles Ansible
monitoring/prometheus/       Configuration Prometheus
monitoring/grafana/          Datasource et dashboard Grafana
docs/                        Documentation projet
data/                        SQL de reference
docker-compose.yml           Stack locale
.env.example                 Exemple de configuration sans secret
```

## Prerequis

- Docker Desktop;
- Docker Compose;
- Git;
- Terraform 1.5+ si execution locale hors conteneur;
- acces Infomaniak Public Cloud;
- key pair OpenStack officielle `cloud-lab-key`;
- cle privee correspondante dans `secrets/cloud-lab-key`;
- floating IP pour les VMs devant etre accessibles en SSH/monitoring.

## Demarrage local

Copier la configuration :

```powershell
copy .env.example .env
```

Demarrer la stack :

```powershell
docker compose up -d --build
```

URLs utiles :

```text
Portail       http://localhost:8080/portal/
API Swagger   http://localhost:8000/docs
Prometheus    http://localhost:9090
Grafana       http://localhost:3000
```

Arret :

```powershell
docker compose down
```

## Authentification

### Mode developpement

Le mode `mock` sert uniquement a la demonstration locale et au developpement.

Comptes de demonstration :

| Email | Mot de passe | Role |
|---|---|---|
| `auguy.mabika@git.swiss` | `admin123` | admin |
| `josue.projet@git.swiss` | `validator123` | validator |
| `lorenzo.reseau@git.swiss` | `teacher123` | teacher |
| `rayan.terraform@git.swiss` | `student123` | student |

Exemple API :

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "auguy.mabika@git.swiss",
  "password": "admin123"
}
```

### Mode production

La production doit utiliser Microsoft Entra ID / OIDC :

```env
AUTH_MODE=oidc
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_REDIRECT_URI=https://<domaine>/api/v1/auth/callback
```

Les comptes mock ne doivent pas etre utilises en production finale.

## Variables importantes

Exemple minimal pour le backend :

```env
ENVIRONMENT=development
AUTH_MODE=mock
DATABASE_URL=postgresql+asyncpg://cloud_lab_dev:cloud_lab_dev_password@postgres:5432/cloud_lab
SESSION_SECRET=change-me
PROVISIONER_MODE=terraform
REAL_PROVISIONING_ENABLED=true
```

OpenStack / Infomaniak :

```env
OS_AUTH_URL=https://api.pub1.infomaniak.cloud/identity/v3
OS_PROJECT_NAME=Projet-ALJ
OS_USERNAME=PCU-B8MJTY2
OS_PASSWORD=...
OS_REGION_NAME=dc4-a
OPENSTACK_KEYPAIR_NAME=cloud-lab-key
OPENSTACK_SECURITY_GROUP_NAME=sg-student-vm
OPENSTACK_AVAILABILITY_ZONE=az-1
```

Terraform :

```env
TERRAFORM_MODULE_DIR=/app/infrastructure
TERRAFORM_WORK_DIR=/app/.terraform-runs
TERRAFORM_PROJECT_PREFIX=cloud-lab
TERRAFORM_NETWORK_CIDR=10.42.0.0/24
TERRAFORM_EXTERNAL_NETWORK_NAME=ext-floating1
TERRAFORM_ASSIGN_FLOATING_IP=true
TERRAFORM_ALLOWED_SSH_CIDRS=["<IP_PUBLIQUE_GIT_OU_VPN>/32"]
TERRAFORM_ALLOWED_NODE_EXPORTER_CIDRS=["<IP_PUBLIQUE_PROMETHEUS_OU_VPN>/32"]
```

Ansible :

```env
ANSIBLE_ENABLED=true
ANSIBLE_SSH_USER=ubuntu
ANSIBLE_SSH_PRIVATE_KEY_PATH=/app/secrets/cloud-lab-key
ANSIBLE_TIMEOUT_SECONDS=900
```

## Workflow de provisioning

1. L'utilisateur cree une demande de VM.
2. La demande passe en attente de validation.
3. Un admin ou validateur approuve la demande.
4. Le backend cree la VM avec Terraform sur Infomaniak OpenStack.
5. La VM passe en statut `configuring`.
6. Ansible se connecte en SSH avec `cloud-lab-key`.
7. Ansible installe les outils du template.
8. Ansible installe `prometheus-node-exporter`.
9. La VM passe en statut `running`.
10. Prometheus recupere les metriques par VM.
11. Le scheduler detruit la VM a sa date de fin.

## Templates Ansible

Role commun `base` :

- attente SSH;
- `apt update`;
- installation de `python3`, `git`, `curl`, `vim`, `htop`;
- creation de l'utilisateur `student`;
- droits sudo;
- MOTD avec nom VM, cours et date de fin;
- installation et activation de `prometheus-node-exporter`.

Roles specialises :

| Template | Outils installes |
|---|---|
| Administration Linux | openssh-server, net-tools, ufw, fail2ban |
| Developpement Web | nodejs, npm, nginx |
| Science des donnees | python3-pip, jupyter, pandas, numpy |
| Laboratoire cybersecurite | nmap, netcat, wireshark-common, john |

Si Ansible echoue, la VM passe en `error`. Le parc VM affiche alors un bouton **Relancer Ansible** pour relancer la configuration sans recreer la VM.

## Monitoring

Le backend expose les metriques applicatives :

```text
GET /metrics
```

Prometheus recupere aussi les VMs actives via service discovery :

```text
GET /metrics/vm-targets
```

Les VMs sont scrapees sur :

```text
<floating-ip-vm>:9100
```

Pour que le monitoring par VM fonctionne :

- la VM doit avoir une IP joignable par Prometheus;
- `node_exporter` doit etre installe par Ansible;
- le security group doit autoriser TCP `9100` depuis l'IP Prometheus uniquement.

## Infrastructure Terraform

Le dossier `infrastructure/` gere :

- reseau prive;
- subnet;
- routeur;
- security group;
- regles SSH, ICMP et node_exporter;
- key pair OpenStack;
- VMs Ubuntu 24.04;
- floating IP optionnelle;
- outputs de provisioning.

Commandes classiques :

```powershell
cd infrastructure
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
terraform destroy
```

Dans l'application, Terraform est appele par le backend. L'utilisateur ne lance pas Terraform manuellement pendant le workflow normal.

## API principale

```http
POST /api/v1/auth/login
GET  /api/v1/auth/me
GET  /api/v1/courses
GET  /api/v1/vm-templates
POST /api/v1/vm-requests
POST /api/v1/vm-requests/{id}/approve
POST /api/v1/vm-requests/{id}/reject
GET  /api/v1/virtual-machines
POST /api/v1/virtual-machines/{id}/destroy
POST /api/v1/virtual-machines/{id}/retry-ansible
GET  /api/v1/dashboard/summary
GET  /api/v1/audit-events
GET  /api/v1/notifications
GET  /metrics
GET  /metrics/vm-targets
```

Documentation interactive :

```text
http://localhost:8000/docs
```

## Securite

Ne jamais commit :

- `.env`;
- `secrets/`;
- `cloud-lab-key`;
- `clouds.yaml`;
- `terraform.tfvars`;
- `*.tfstate`;
- credentials OpenStack;
- secrets Azure / Entra ID.

Regles de production :

- une seule key pair officielle : `cloud-lab-key`;
- SSH par cle uniquement;
- SSH limite a l'IP GIT/VPN/admin, pas `0.0.0.0/0`;
- port `9100` limite a Prometheus/VPN;
- OIDC obligatoire en production;
- roles applicatifs stricts;
- audit active sur les actions sensibles;
- destruction automatique activee pour eviter les couts oublies.

## Demonstration technique

Scenario conseille :

1. Se connecter comme admin.
2. Creer une demande VM avec date de fin.
3. Approuver la demande.
4. Montrer l'audit : `request_created`, `request_approved`, `vm_created`.
5. Montrer la VM sur Horizon Infomaniak.
6. Montrer l'audit Ansible : `vm_ansible_started`, `vm_ansible_completed`.
7. Montrer le parc VM avec la VM active.
8. Montrer Prometheus/Grafana.
9. Detruire la VM depuis le site.
10. Verifier la suppression dans Horizon.

## Equipe

| Personne | Responsabilite principale |
|---|---|
| Auguy Mabika | Frontend, backend FastAPI, workflow applicatif, dashboard, couts, audit, integration globale |
| Josue | Infrastructure cloud, provisioning OpenStack, validation de la chaine Terraform |
| Lorenzo | Reseau, securite, isolation, security groups, acces SSH |
| Rayan | Terraform, automatisation infrastructure, premiers outputs de provisioning |

Cette section est utile pour la soutenance : elle montre clairement la repartition des responsabilites et evite de melanger les perimetres.

## Troubleshooting

### La VM est creee mais Ansible echoue

Verifier :

- floating IP presente;
- security group autorise SSH depuis l'IP du backend;
- key pair OpenStack = `cloud-lab-key`;
- cle privee presente dans `secrets/cloud-lab-key`;
- `ANSIBLE_SSH_USER=ubuntu`.

Puis utiliser le bouton **Relancer Ansible** dans le parc VM.

### Prometheus ne voit pas la VM

Verifier :

- Ansible a installe `prometheus-node-exporter`;
- le port `9100` est ouvert uniquement depuis Prometheus;
- `/metrics/vm-targets` retourne la VM;
- la VM a une IP joignable par Prometheus.

### Terraform retourne `Authentication failed`

Verifier :

- `OS_USERNAME`;
- `OS_PASSWORD`;
- `OS_PROJECT_NAME`;
- `OS_AUTH_URL`;
- `OS_REGION_NAME`;
- mot de passe OpenStack dedie, pas forcement le mot de passe du compte web Infomaniak.

### Docker ne redemarre pas

```powershell
docker compose down
docker compose up -d --build
```

### Le frontend ne change pas

Recharger sans cache :

```text
Ctrl + F5
```

## Licence

Projet academique realise dans le cadre du hackathon GIT x Satom IT, juin 2026.
