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
- `type` : categorie fonctionnelle (`vm_request_approved`, `vm_request_refused`, `vm_expiring_soon`, `vm_destroyed`).
- `title` / `message` : contenu affichable dans le portail.
- `is_read` : suivi lu/non lu.
- `metadata` : contexte technique extensible (`request_id`, `vm_id`, `end_date`) pour eviter les doublons et relier la notification au cycle de vie.
- `created_at` : horodatage serveur.

Flux implemente :

- Lorsqu'une demande VM est approuvee ou refusee via `PATCH /api/v1/vm-requests/:id`, le demandeur recoit automatiquement une notification.
- Lorsqu'une VM passe au statut `destroyed`, le proprietaire recoit une notification `vm_destroyed`.
- Un job `node-cron` tourne chaque jour a 08:00 et cree une notification `vm_expiring_soon` pour les VM dont l'echeance est proche, en evitant les doublons pour une meme VM le meme jour.

Endpoints :

```http
GET /api/v1/notifications
GET /api/v1/notifications?unread_only=true
PATCH /api/v1/notifications/:id/read
```

Un adaptateur email existe dans `server/src/services/emailAdapter.js`. Pour le pilote, il journalise les emails avec `console.log`. En production, il suffit de remplacer cette implementation par un provider SMTP Infomaniak Mail, SendGrid ou un service interne, sans changer les controleurs.

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
- `GET /api/v1/virtual-machines`
- `PATCH /api/v1/virtual-machines/:id`
- `GET /api/v1/vm-metrics`
- `GET /api/v1/cost-records`
- `GET /api/v1/audit-events`
- `GET /api/v1/notifications`
- `PATCH /api/v1/notifications/:id/read`
- `GET /api/v1/dashboard/summary`
