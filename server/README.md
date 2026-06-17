# Cloud Lab Control Center - Backend

Backend Express + PostgreSQL pour remplacer progressivement la logique en memoire du portail statique.

## Prerequis

- Node.js 20+
- PostgreSQL 15+
- npm

## Installation

```bash
cd server
npm install
```

## Configuration

Copier `.env.example` vers `.env` a la racine du depot, puis adapter les valeurs.

Variable recommandee :

```bash
DATABASE_URL=postgres://cloud_lab_dev:cloud_lab_dev_password@localhost:5432/cloud_lab
PORT=3000
AUTH_MODE=mock
SESSION_SECRET=change-me-with-a-long-random-value
```

Les valeurs ci-dessus sont uniquement des valeurs de developpement local. Ne jamais committer de secret reel.

## Authentification

Le backend supporte deux modes avec les memes endpoints, pour que le frontend ne change pas de contrat.

### Mode mock

Mode recommande pour le developpement local et les demos sans tenant Azure :

```bash
AUTH_MODE=mock
```

Connexion avec un utilisateur de test existant en base :

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "nadia.keller@git.example"
}
```

On peut aussi utiliser `user_id` :

```http
GET /api/v1/auth/login?user_id=1
```

### Mode OIDC Microsoft Entra ID

Mode cible pour les comptes Office 365 du GIT :

```bash
AUTH_MODE=oidc
AZURE_TENANT_ID=<tenant-id>
AZURE_CLIENT_ID=<application-client-id>
AZURE_CLIENT_SECRET=<client-secret>
AZURE_REDIRECT_URI=http://localhost:3000/api/v1/auth/callback
AZURE_SCOPES="openid profile email User.Read"
SESSION_SECRET=<long-secret-aleatoire>
```

Flux :

- `GET /api/v1/auth/login` redirige vers Microsoft Entra ID.
- `GET /api/v1/auth/callback` echange le code OIDC, retrouve ou cree l'utilisateur via son email institutionnel, puis ouvre une session.
- `GET /api/v1/auth/me` retourne l'utilisateur connecte.
- `POST /api/v1/auth/logout` ferme la session.

### App Registration Azure

Dans Microsoft Entra ID :

1. Creer une App Registration.
2. Ajouter une plateforme Web.
3. Ajouter la Redirect URI : `http://localhost:3000/api/v1/auth/callback` en dev, puis l'URL HTTPS de production.
4. Creer un client secret et le placer uniquement dans `.env`.
5. Donner les scopes OpenID Connect : `openid`, `profile`, `email`.
6. Ajouter `User.Read` si le projet doit lire le profil Microsoft Graph.

Les sessions sont stockees en PostgreSQL via un cookie `httpOnly`. En production, le cookie devient `secure` avec `NODE_ENV=production`.

## Notifications

Le backend contient une table `notifications` pour informer les utilisateurs sans coupler le portail a un provider email.

Champs principaux :

- `user_id` : destinataire de la notification.
- `type` : categorie fonctionnelle (`vm_request_approved`, `vm_request_refused`, `vm_expiring_soon`, `vm_expired`, `vm_destroyed`).
- `title` / `message` : contenu affichable dans le portail.
- `is_read` : suivi lu/non lu.
- `metadata` : contexte technique extensible (`request_id`, `vm_id`, `end_date`) pour eviter les doublons et relier la notification au cycle de vie.
- `created_at` : horodatage serveur.

Flux implemente :

- Lorsqu'une demande VM est approuvee ou refusee via `PATCH /api/v1/vm-requests/:id`, le demandeur recoit automatiquement une notification.
- Lorsqu'une VM passe au statut `destroyed`, le proprietaire recoit une notification `vm_destroyed`.
- Un job `node-cron` tourne chaque jour a 08:00. Il marque d'abord les VM arrivees a echeance en `expired`, puis cree une notification `vm_expiring_soon` pour les VM dont l'echeance est proche, en evitant les doublons pour une meme VM le meme jour.

Endpoints :

```http
GET /api/v1/notifications
GET /api/v1/notifications?unread_only=true
PATCH /api/v1/notifications/:id/read
```

Un adaptateur email existe dans `server/src/services/emailAdapter.js`. Pour le pilote, il journalise les emails avec `console.log`. En production, il suffit de remplacer cette implementation par un provider SMTP Infomaniak Mail, SendGrid ou un service interne, sans changer les controleurs.

## Cycle de vie des VM (partie data)

Le backend gere la detection data de fin de vie, mais ne declenche aucune action d'infrastructure.

Chaque jour a 08:00, un job planifie selectionne les `virtual_machines` dont :

- `end_date <= CURRENT_DATE` ;
- `status` n'est pas deja `expired` ;
- `status` n'est pas deja `destroyed`.

Pour chaque VM concernee, le backend :

- met `virtual_machines.status = 'expired'` ;
- cree un `audit_event` de type `vm_expired` ;
- cree une notification `vm_expired` pour le proprietaire de la VM.

Frontiere importante :

- `expired` signifie : la VM est arrivee a echeance cote donnees et doit etre traitee.
- `destroyed` signifie : la destruction reelle a ete confirmee cote cloud.

Le backend ne marque jamais une VM `destroyed` tout seul. Seul le futur code d'infrastructure de Josue, apres suppression reelle dans Infomaniak/OpenStack, appellera :

```http
PATCH /api/v1/virtual-machines/:id/destruction-result
```

Pour afficher les VM arrivees a echeance et en attente de destruction reelle :

```http
GET /api/v1/virtual-machines?status=expired
```

## Monitoring minimal cote donnees

Le backend expose et stocke les metriques VM dans `vm_metrics`, mais ne collecte rien directement sur les machines.

Frontiere importante :

- ce backend recoit, valide et historise les metriques ;
- la collecte reelle sur les VM physiques ou cloud sera branchee plus tard par l'equipe infra ;
- aucun SSH, aucun agent installe et aucun appel reseau vers une VM n'est effectue ici.

### Envoyer une mesure pour une VM

```http
POST /api/v1/virtual-machines/:id/metrics
Content-Type: application/json
```

Role autorise pour l'instant : `admin`. Plus tard, ce sera un compte de service technique utilise par un agent de monitoring.

Payload :

```json
{
  "cpu_usage_percent": 42.5,
  "ram_usage_percent": 68.1,
  "disk_usage_percent": 51.9,
  "state": "up"
}
```

Valeurs acceptees pour `state` :

- `up`
- `down`
- `unknown`

Comportement :

- verifie que la VM existe ;
- insere une ligne dans `vm_metrics` ;
- cree un `audit_event` de type `vm_metric_received`.

Codes de retour :

- `201` : metrique enregistree ;
- `400` : payload invalide ;
- `404` : VM introuvable ;
- `401/403` : utilisateur non connecte ou role insuffisant.

### Historique des metriques d'une VM

```http
GET /api/v1/virtual-machines/:id/metrics/history
GET /api/v1/virtual-machines/:id/metrics/history?limit=100
```

Le parametre `limit` est optionnel, borne entre 1 et 500. Par defaut, l'API retourne les 50 derniers points.

### Simulation de metriques pour demo

Pour tester le dashboard sans vraie VM ni agent de monitoring :

```bash
cd server
npm run simulate-metrics
```

Ce script insere des metriques aleatoires plausibles pour les VM en status `running`.

Important : `server/scripts/simulate-metrics.js` est un outil de developpement/demo. Ce n'est pas un composant de production et il ne remplace pas la collecte reelle qui sera branchee plus tard par Josue/Lorenzo.

## Integration future provisioning

Cette API prepare le contrat entre le portail Cloud Lab et le futur service de provisioning Terraform/OpenTofu de Josue.

Important : le backend ne lance aucune commande Terraform, aucun `execFile`, aucun SSH et ne cree aucune VM reelle. Les routes ci-dessous changent uniquement des statuts en base, ecrivent des evenements d'audit et exposent un contrat stable pour l'integration future.

### 1. Demander le provisioning d'une demande approuvee

```http
POST /api/v1/vm-requests/:id/provision
```

Role autorise : `validator` ou `admin`.

Comportement :

- verifie que la demande existe ;
- verifie que `vm_requests.status = 'approved'` ;
- passe la demande a `status = 'provisioning'` ;
- cree un `audit_event` de type `provisioning_requested` ;
- retourne `202 Accepted`.

Reponse :

```json
{
  "data": {
    "id": 12,
    "status": "provisioning"
  }
}
```

Codes de retour :

- `202` : intention de provisioning enregistree ;
- `404` : demande introuvable ;
- `409` : demande pas encore approuvee ;
- `401/403` : utilisateur non connecte ou role insuffisant.

### 2. Rapporter le resultat du provisioning reel

```http
PATCH /api/v1/virtual-machines/:id/provisioning-result
Content-Type: application/json
```

Role autorise pour l'instant : `admin`. Plus tard, ce sera un compte de service technique.

Payload :

```json
{
  "provider_vm_id": "infomaniak-openstack-vm-id",
  "ip_address": "10.42.0.15",
  "status": "running",
  "network_segment": "class-linux-admin"
}
```

Valeurs acceptees pour `status` :

- `running` : provisioning reussi, audit `vm_provisioned` ;
- `error` : provisioning echoue, audit `vm_provisioning_failed`.

Comportement :

- met a jour `provider_vm_id`, `ip_address`, `status`, `network_segment` ;
- cree un evenement d'audit `vm_provisioned` ou `vm_provisioning_failed`.

Codes de retour :

- `200` : resultat enregistre ;
- `400` : payload invalide ;
- `404` : VM introuvable ;
- `401/403` : utilisateur non connecte ou role insuffisant.

### 3. Rapporter le resultat de destruction

```http
PATCH /api/v1/virtual-machines/:id/destruction-result
Content-Type: application/json
```

Role autorise pour l'instant : `admin`. Plus tard, ce sera un compte de service technique.

Payload :

```json
{
  "status": "destroyed",
  "destroyed_at": "2026-06-18T10:30:00.000Z"
}
```

`destroyed_at` est optionnel. S'il est absent, le serveur utilise l'heure courante.

Comportement :

- passe la VM a `status = 'destroyed'` ;
- renseigne `destroyed_at` ;
- cree un `audit_event` de type `vm_destroyed` ;
- cree une notification `vm_destroyed` pour le proprietaire de la VM.

Codes de retour :

- `200` : destruction enregistree ;
- `400` : payload invalide ;
- `404` : VM introuvable ;
- `401/403` : utilisateur non connecte ou role insuffisant.

## Migrations

```bash
cd server
npm run migrate
```

## Seed

```bash
cd server
npm run seed
```

## Demarrage

```bash
cd server
npm run dev
```

API disponible sur :

```text
http://localhost:3000/api/v1
```

Healthcheck :

```text
GET /health
```

## Docker Compose local

Depuis la racine du depot :

```bash
docker compose up --build
```

Le service PostgreSQL expose le port `5432`, le backend expose le port `3000`.

## Endpoints principaux

- `GET /api/v1/auth/login`
- `POST /api/v1/auth/login` (mode mock)
- `GET /api/v1/auth/callback`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users`
- `POST /api/v1/users`
- `GET /api/v1/courses`
- `GET /api/v1/vm-templates`
- `GET /api/v1/vm-requests`
- `POST /api/v1/vm-requests`
- `PATCH /api/v1/vm-requests/:id`
- `POST /api/v1/vm-requests/:id/provision`
- `GET /api/v1/virtual-machines`
- `GET /api/v1/virtual-machines?status=expired`
- `PATCH /api/v1/virtual-machines/:id`
- `POST /api/v1/virtual-machines/:id/metrics`
- `GET /api/v1/virtual-machines/:id/metrics/history`
- `PATCH /api/v1/virtual-machines/:id/provisioning-result`
- `PATCH /api/v1/virtual-machines/:id/destruction-result`
- `GET /api/v1/vm-metrics`
- `GET /api/v1/cost-records`
- `GET /api/v1/audit-events`
- `GET /api/v1/notifications`
- `PATCH /api/v1/notifications/:id/read`
- `GET /api/v1/dashboard/summary`
