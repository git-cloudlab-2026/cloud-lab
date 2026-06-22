# Cloud Lab

Plateforme de gestion de VMs educatives pour le Geneva Institute of Technology.

Cloud Lab permet a un etudiant ou a un formateur de demander une VM temporaire, de faire valider cette demande, de provisionner l'environnement sur Infomaniak Public Cloud, de suivre les couts et de nettoyer automatiquement les machines arrivees a echeance.

```text
Demande -> Validation -> Provisioning -> Configuration -> Monitoring -> Fin de vie
```

## Fonctionnalites principales

- portail web pour demander une ou plusieurs VMs de cours;
- catalogue de templates : Linux admin, developpement web, data science, securite;
- workflow de validation/refus avec roles;
- authentification JWT locale pour le developpement;
- integration Microsoft Entra ID / OIDC preparee pour la production;
- API FastAPI versionnee `/api/v1`;
- base PostgreSQL en production et via Docker Compose en developpement;
- couche data : demandes, VMs, couts, metriques, audit, notifications;
- scheduler de fin de vie pour marquer les VMs expirees;
- MockTerraformService pour tester sans acces OpenStack;
- Terraform/OpenTofu pour Infomaniak OpenStack;
- Ansible pour le durcissement SSH et la configuration initiale;
- documentation OpenAPI/Swagger automatique.

## Architecture

```mermaid
flowchart LR
  U["Etudiant / Formateur"] --> F["Frontend web\n(portail statique actuel, React-ready)"]
  F --> A["API FastAPI\n/api/v1"]
  A --> DB["PostgreSQL\nusers, requests, VMs, costs, audit"]
  A --> AUTH["JWT dev\nOIDC Entra ID prod"]
  A --> S["Scheduler\nexpiration VMs"]
  A --> M["MockTerraformService\ndemo sans infra"]
  A --> P["Provisioner futur"]
  P --> T["Terraform / OpenTofu"]
  T --> O["Infomaniak Public Cloud\nOpenStack"]
  O --> VM["VMs Ubuntu"]
  VM --> AN["Ansible\nSSH hardening"]
```

## Prerequis

- Python 3.11 ou 3.12;
- Docker Desktop et Docker Compose;
- Terraform ou OpenTofu 1.5+;
- Git;
- Node.js 18+ si le frontend evolue vers React;
- acces Infomaniak Public Cloud pour le provisioning reel;
- une cle SSH publique locale, par exemple `~/.ssh/id_ed25519.pub`.

## Structure du projet

```text
app/                       Portail web HTML/CSS/JS
server/                    Backend FastAPI, SQLAlchemy, Alembic
data/                      Schema SQL de reference, seed, requetes dashboard
infrastructure/            Terraform/OpenTofu Infomaniak OpenStack
ansible/                   Playbook et role SSH hardening
docs/                      Documentation technique
.github/workflows/ci.yml   Pipeline CI GitHub Actions
docker-compose.yml         PostgreSQL + API locale
.env.example               Exemple de configuration sans secret
Makefile                   Commandes utiles
README.md                  Documentation principale
```

## Configuration

Copier le fichier d'exemple :

```powershell
Copy-Item .env.example .env
```

Adapter ensuite `.env` localement. Ne jamais commit `.env`.

Variables importantes :

```text
AUTH_MODE=mock
DATABASE_URL=postgresql+asyncpg://cloud_lab_dev:cloud_lab_dev_password@localhost:5432/cloud_lab
JWT_SECRET=change-me
SESSION_SECRET=change-me
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
AZURE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
```

En production :

```text
ENVIRONMENT=production
AUTH_MODE=oidc
```

## Installation locale avec Docker

Commande recommandee pour tester tout le backend :

```powershell
docker compose up --build
```

Le conteneur backend lance :

1. les migrations Alembic;
2. le seed de donnees demo;
3. FastAPI sur le port `8000`.

URLs utiles :

```text
Portail web      http://localhost:8000/portal/
Swagger OpenAPI  http://localhost:8000/docs
Healthcheck      http://localhost:8000/health
```

Arret :

```powershell
docker compose down
```

## Installation locale sans Docker

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Commandes Make

Si `make` est disponible :

```powershell
make up
make logs
make migrate
make seed
make test
make infra-init
make infra-plan
```

Sous Windows sans `make`, utiliser directement les commandes Docker, Python et Terraform indiquees dans ce README.

## Authentification

### Mode developpement : JWT local

Comptes de demonstration :

| Email | Mot de passe | Role |
|---|---|---|
| `admin@giptech.ch` | `admin123` | admin |
| `prof@giptech.ch` | `prof123` | teacher |
| `etudiant1@giptech.ch` | `etu123` | student |

Exemple :

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@giptech.ch",
  "password": "admin123"
}
```

Puis envoyer :

```http
Authorization: Bearer <token>
```

### Mode production : Microsoft Entra ID / OIDC

Le mode OIDC est prepare mais depend des acces GIT :

- Tenant ID;
- Client ID;
- Client Secret;
- Redirect URI;
- groupes Entra pour mapper les roles.

Scopes prevus :

```text
openid profile email User.Read GroupMember.Read.All
```

Mapping prevu :

```text
Admin / Validateurs / Enseignants / E1 / E2 / E3 / E4 / E5
```

## Deploiement infrastructure

Le dossier `infrastructure/` cree :

- reseau prive;
- sous-reseau;
- routeur;
- security group SSH/ICMP;
- paire de cles SSH;
- VMs Ubuntu;
- floating IPs optionnelles;
- outputs : VM IDs, noms, IPs, commandes SSH.

Configuration :

```powershell
cd infrastructure
Copy-Item terraform.tfvars.example terraform.tfvars
```

Remplir `terraform.tfvars` avec les valeurs Infomaniak/OpenStack :

```hcl
auth_url            = "https://api.pub1.infomaniak.cloud/identity/v3"
region              = "dc4-a"
project_name        = "Projet-ALJ"
username            = "PCU-XXXX"
password            = "CHANGE_ME"
external_network_id = "CHANGE_ME_EXTERNAL_NETWORK_ID"
```

Commandes :

```powershell
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
terraform output
```

Destruction :

```powershell
terraform destroy
```

## Utilisation du workflow

1. L'utilisateur se connecte au portail.
2. Il choisit un template de VM et une date de fin.
3. Une demande est creee avec un cout estime.
4. Un validateur approuve ou refuse.
5. En mode demo, `MockTerraformService` cree une VM simulee.
6. En production, un provisioner externe appelle Terraform/OpenTofu.
7. Le dashboard suit VMs, couts, alertes et audit.
8. Le scheduler marque les VMs expirees.
9. La destruction reelle est confirmee via l'API.

## API Documentation

Documentation interactive :

```text
http://localhost:8000/docs
```

Endpoints principaux :

```http
POST /api/v1/auth/login
GET  /api/v1/auth/me
GET  /api/v1/courses
GET  /api/v1/vm-templates
GET  /api/v1/vm-requests
POST /api/v1/vm-requests
POST /api/v1/vm-requests/{id}/approve
POST /api/v1/vm-requests/{id}/reject
GET  /api/v1/virtual-machines
POST /api/v1/virtual-machines/{id}/metrics
GET  /api/v1/dashboard/summary
GET  /api/v1/audit-events
GET  /api/v1/notifications
```

Voir aussi :

```text
docs/api.md
```

## CI/CD

Le pipeline GitHub Actions `.github/workflows/ci.yml` verifie :

- installation Python;
- compilation backend;
- tests backend;
- format Terraform;
- `terraform init -backend=false`;
- `terraform validate`.

## Securite

- ne jamais commit `.env`, `terraform.tfvars`, `*.tfstate`, cle SSH privee ou `clouds.yaml`;
- JWT signe avec secret configurable;
- OIDC obligatoire en production;
- roles applicatifs : student, teacher, validator, admin;
- routes sensibles protegees par role;
- 2FA a activer sur les comptes GitHub, Infomaniak et Microsoft;
- SSH par cle uniquement cote infrastructure;
- `allowed_ssh_cidr` doit etre restreint en production.

## Equipe et roles

| Personne | Role projet |
|---|---|
| Auguy | Portail, backend, data, dashboard, couts, audit, notifications, coordination technique |
| Josue | Terraform/OpenTofu, provisioning reel, destruction reelle |
| Lorenzo | Reseau, securite, isolation, SSH, Ansible |

## Troubleshooting

### `terraform` n'est pas reconnu

Installer Terraform puis rouvrir le terminal :

```powershell
terraform version
```

### `Authentication failed` avec OpenStack

Verifier :

- `username`;
- `password`;
- `project_name`;
- `auth_url`;
- `region`;
- mot de passe OpenStack specifique, pas forcement le mot de passe du compte web.

### `No outputs found`

Executer d'abord :

```powershell
terraform apply
terraform output
```

### Docker ne demarre pas PostgreSQL

Verifier que Docker Desktop est lance, puis :

```powershell
docker compose down
docker compose up --build
```

### Les changements frontend ne se voient pas

Recharger sans cache :

```text
Ctrl + F5
```

Puis verifier que l'URL est :

```text
http://localhost:8000/portal/
```

## License

Projet academique realise dans le cadre du hackathon GIT x Satom IT, juin 2026.
