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
```

Les valeurs ci-dessus sont uniquement des valeurs de developpement local. Ne jamais committer de secret reel.

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
- `GET /api/v1/dashboard/summary`
