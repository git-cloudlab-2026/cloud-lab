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
AZURE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger :

```text
http://localhost:8000/docs
```

Portail frontend servi par le backend :

```text
http://localhost:8000/portal/
```

Cette URL est a utiliser pour tester la connexion et les sessions. Eviter `file://`
pour les tests backend, car les cookies de session ne sont pas fiables hors HTTP.

## Authentification Microsoft Entra ID

Deux modes existent :

- `AUTH_MODE=mock` : developpement local sans tenant Azure;
- `AUTH_MODE=oidc` : connexion reelle Microsoft Entra ID.

En `ENVIRONMENT=production`, le backend refuse de demarrer si `AUTH_MODE` n'est pas `oidc`.

Connexion de developpement :

```http
POST /api/v1/auth/mock-login/1
```

Connexion JWT locale pour tester l'API sans navigateur ni Entra ID :

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@giptech.ch",
  "password": "admin123"
}
```

Comptes disponibles en `AUTH_MODE=mock` :

| Email | Mot de passe | Role |
|---|---|---|
| `admin@giptech.ch` | `admin123` | `admin` |
| `prof@giptech.ch` | `prof123` | `teacher` |
| `etudiant1@giptech.ch` | `etu123` | `student` |

Le token retourne doit ensuite etre envoye avec :

```http
Authorization: Bearer <token>
```

Session courante :

```http
GET /api/v1/auth/me
```

### Activer Entra ID reel

Dans `.env` :

```env
AUTH_MODE=oidc
SESSION_SECRET=une-valeur-longue-aleatoire
AZURE_TENANT_ID=<tenant-id-git>
AZURE_CLIENT_ID=<application-client-id>
AZURE_CLIENT_SECRET=<client-secret>
AZURE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
AZURE_SCOPES=openid profile email User.Read GroupMember.Read.All
ENTRA_ADMIN_GROUP_ID=<object-id-groupe-admin>
ENTRA_VALIDATOR_GROUP_ID=<object-id-groupe-validateurs>
ENTRA_TEACHER_GROUP_ID=<object-id-groupe-enseignants>
ENTRA_STUDENT_E1_GROUP_ID=<object-id-groupe-e1>
ENTRA_STUDENT_E2_GROUP_ID=<object-id-groupe-e2>
ENTRA_STUDENT_E3_GROUP_ID=<object-id-groupe-e3>
ENTRA_STUDENT_E4_GROUP_ID=<object-id-groupe-e4>
ENTRA_STUDENT_E5_GROUP_ID=<object-id-groupe-e5>
OIDC_AUTO_CREATE_STUDENTS=true
```

Routes du flux OIDC :

```http
GET /api/v1/auth/login
GET /api/v1/auth/callback
POST /api/v1/auth/logout
GET /api/v1/auth/me
```

Comportement :

1. `/login` redirige vers Microsoft Entra ID.
2. Microsoft rappelle `/callback` avec un `code`.
3. Le backend echange le code contre des tokens.
4. Le `id_token` est verifie avec les cles JWKS Microsoft.
5. Les groupes Entra ID sont compares au mapping configure.
6. L'email institutionnel est cherche dans la table `users`.
7. Si l'utilisateur existe et est actif, une session serveur est ouverte.
8. Si l'utilisateur est un etudiant E1-E5 inconnu, il peut etre cree automatiquement avec le role `student`.

### Mapping groupes Entra ID

Le portail gere 5 classes :

```text
E1, E2, E3, E4, E5
```

Chaque classe contient 25 etudiants dans les donnees de demonstration.

Mapping prevu :

| Groupe Entra ID | Role applicatif | Classe |
|---|---|---|
| `ENTRA_ADMIN_GROUP_ID` | `admin` | - |
| `ENTRA_VALIDATOR_GROUP_ID` | `validator` | - |
| `ENTRA_TEACHER_GROUP_ID` | `teacher` | - |
| `ENTRA_STUDENT_E1_GROUP_ID` | `student` | `E1` |
| `ENTRA_STUDENT_E2_GROUP_ID` | `student` | `E2` |
| `ENTRA_STUDENT_E3_GROUP_ID` | `student` | `E3` |
| `ENTRA_STUDENT_E4_GROUP_ID` | `student` | `E4` |
| `ENTRA_STUDENT_E5_GROUP_ID` | `student` | `E5` |

Securite volontaire :

- les etudiants peuvent etre crees automatiquement au premier login si leur groupe Entra indique E1-E5;
- les roles sensibles (`admin`, `validator`, `teacher`) doivent deja exister dans la table `users`;
- si un role Entra ne correspond pas au role applicatif en base, l'acces est refuse.

Pour que les groupes soient presents dans le `id_token`, l'App Registration Entra ID doit etre configuree pour inclure les groupes dans les tokens. Si l'organisation prefere ne pas exposer les groupes dans le token, une phase suivante peut interroger Microsoft Graph avec `GroupMember.Read.All`.

### App Registration Azure

Dans Microsoft Entra ID :

1. Creer une **App Registration**.
2. Choisir une application web.
3. Ajouter la Redirect URI :

```text
http://localhost:8000/api/v1/auth/callback
```

4. Copier `Application (client) ID` dans `AZURE_CLIENT_ID`.
5. Copier `Directory (tenant) ID` dans `AZURE_TENANT_ID`.
6. Creer un client secret et le mettre dans `AZURE_CLIENT_SECRET`.
7. Autoriser les scopes OIDC standards :

```text
openid profile email User.Read GroupMember.Read.All
```

Important : le backend ne donne pas automatiquement un role sensible a un utilisateur inconnu. Les droits du portail restent controles par la base applicative et par le mapping des groupes Entra ID.

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

Le backend ne cree aucune VM reelle lui-meme.

En developpement, `MockTerraformService` simule OpenTofu/Terraform pour tester le
workflow de bout en bout sans acces Infomaniak OpenStack. Il retourne un id
provider fictif, une IP privee, un nom de VM, un segment reseau et un fingerprint
SSH coherents.

Routes de demonstration locale :

```http
POST /api/v1/vm-requests/{id}/approve
POST /api/v1/vm-requests/{id}/reject
POST /api/v1/virtual-machines/{id}/destroy
GET  /api/v1/virtual-machines/expired
```

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
