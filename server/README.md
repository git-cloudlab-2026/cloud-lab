# Backend FastAPI - Cloud Lab Control Center

Backend FastAPI + PostgreSQL pour une architecture plus propre, testable et proche production.

## Architecture

```text
server/
  app/
    api/v1/routes/      Endpoints HTTP
    core/               Configuration, securite, erreurs
    db/                 Session SQLAlchemy
    domain/             Modeles ORM et enums metier
    repositories/       Acces PostgreSQL
    schemas/            Validation Pydantic
    services/           Regles metier
    jobs/               Taches data planifiables
  alembic/              Migrations PostgreSQL
  scripts/              Seed et outils de demonstration
```

La logique respecte une separation simple :

- `routes` : recoivent les requetes HTTP;
- `schemas` : valident les payloads;
- `services` : portent les regles metier;
- `repositories` : isolent les acces base de donnees;
- `domain` : decrit les objets persistants.

Les routes ne doivent pas contenir de logique metier lourde. C'est ce qui rend le backend plus conforme a SOLID : chaque couche a une responsabilite claire.

## Installation locale

Version Python recommandee : `3.12`.

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Copier `.env.example` vers `.env` puis adapter les valeurs.

Variables principales :

```env
DATABASE_URL=postgresql+asyncpg://cloud_lab_dev:cloud_lab_dev_password@localhost:5432/cloud_lab
AUTH_MODE=mock
SESSION_SECRET=change-me
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_REDIRECT_URI=http://localhost:3000/api/v1/auth/callback
```

## Migrations et seed

```powershell
cd server
alembic upgrade head
python -m scripts.seed
```

## Lancer l'API

Le plus fiable en developpement est Docker, car l'image utilise Python 3.12 :

```powershell
docker compose up --build
```

En local sans Docker :

```powershell
cd server
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

Swagger :

```text
http://localhost:3000/docs
```

## Authentification

Mode actuel : `AUTH_MODE=mock`.

Connexion de developpement :

```http
POST /api/v1/auth/mock-login/1
```

Session courante :

```http
GET /api/v1/auth/me
```

OIDC Entra ID reel :

- configuration prevue dans `.env.example`;
- routes reservees : `/api/v1/auth/login` et `/api/v1/auth/callback`;
- integration finale a brancher quand le tenant Azure/Entra du GIT est disponible.

## Routes principales

- `GET /api/v1/users`
- `POST /api/v1/users`
- `GET /api/v1/courses`
- `GET /api/v1/vm-templates`
- `GET /api/v1/vm-requests`
- `POST /api/v1/vm-requests`
- `PATCH /api/v1/vm-requests/{id}`
- `POST /api/v1/vm-requests/{id}/provision`
- `GET /api/v1/virtual-machines`
- `PATCH /api/v1/virtual-machines/{id}`
- `PATCH /api/v1/virtual-machines/{id}/provisioning-result`
- `PATCH /api/v1/virtual-machines/{id}/destruction-result`
- `POST /api/v1/virtual-machines/{id}/metrics`
- `GET /api/v1/virtual-machines/{id}/metrics/history`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/audit-events`
- `GET /api/v1/notifications`

## Integration future provisioning

Le backend ne cree aucune VM lui-meme.

Il prepare seulement le contrat que la partie Terraform/OpenTofu de Josue utilisera :

### Demander le provisioning

```http
POST /api/v1/vm-requests/{id}/provision
```

Condition : la demande doit etre `approved`.

Effet : la demande passe en `provisioning`, un audit `provisioning_requested` est cree, puis l'API retourne `202 Accepted`.

### Rapporter le resultat du provisioning

```http
PATCH /api/v1/virtual-machines/{id}/provisioning-result
Content-Type: application/json

{
  "provider_vm_id": "ik-vm-123",
  "ip_address": "10.42.0.15",
  "status": "running",
  "network_segment": "IT-2026-A"
}
```

Effet : la VM est mise a jour, puis un audit `vm_provisioned` ou `vm_provisioning_failed` est cree selon le statut.

### Rapporter la destruction reelle

```http
PATCH /api/v1/virtual-machines/{id}/destruction-result
Content-Type: application/json

{
  "status": "destroyed",
  "destroyed_at": "2026-06-26T18:00:00Z"
}
```

Effet : la VM passe en `destroyed`, la date de destruction est stockee, un audit `vm_destroyed` et une notification sont crees.

## Cycle de vie des VM - partie data

Le backend peut marquer une VM comme `expired` quand sa `end_date` est depassee.

Commande manuelle de developpement :

```powershell
cd server
python -m scripts.mark_expired_vms
```

Frontiere importante :

- `expired` = la VM doit etre detruite;
- `destroyed` = la ressource cloud a vraiment ete supprimee par l'infra.

Le passage a `destroyed` doit venir du futur code Terraform/OpenTofu via la route `destruction-result`.

## Monitoring minimal

Le backend expose :

```http
POST /api/v1/virtual-machines/{id}/metrics
GET /api/v1/virtual-machines/{id}/metrics/history
```

Un script de demonstration permet d'alimenter la table `vm_metrics` sans vraie VM :

```powershell
cd server
python -m scripts.simulate_metrics
```

Ce script sert uniquement au developpement et a la demo. La collecte reelle sera branchee plus tard par l'equipe infra.
