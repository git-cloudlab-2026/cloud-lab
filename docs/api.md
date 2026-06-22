# API Cloud Lab

Base URL locale :

```text
http://localhost:8000/api/v1
```

Documentation interactive :

```text
http://localhost:8000/docs
```

## Authentification

### Login JWT local

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@giptech.ch",
  "password": "admin123"
}
```

La reponse contient un `access_token`.

```http
Authorization: Bearer <token>
```

### OIDC Microsoft Entra ID

```http
GET /api/v1/auth/login
GET /api/v1/auth/callback
POST /api/v1/auth/logout
GET /api/v1/auth/me
```

Le mode OIDC est active avec `AUTH_MODE=oidc` et les variables Azure dans `.env`.

## Catalogue

```http
GET /api/v1/courses
GET /api/v1/vm-templates
```

## Demandes VM

```http
GET /api/v1/vm-requests
POST /api/v1/vm-requests
PATCH /api/v1/vm-requests/{id}
POST /api/v1/vm-requests/{id}/approve
POST /api/v1/vm-requests/{id}/reject
POST /api/v1/vm-requests/{id}/provision
```

## Machines virtuelles

```http
GET /api/v1/virtual-machines
GET /api/v1/virtual-machines/expired
GET /api/v1/virtual-machines/{id}
PATCH /api/v1/virtual-machines/{id}
POST /api/v1/virtual-machines/{id}/destroy
PATCH /api/v1/virtual-machines/{id}/provisioning-result
PATCH /api/v1/virtual-machines/{id}/destruction-result
```

## Monitoring

```http
POST /api/v1/virtual-machines/{id}/metrics
GET /api/v1/virtual-machines/{id}/metrics/history
GET /api/v1/vm-metrics
```

## Dashboard, couts, audit, notifications

```http
GET /api/v1/dashboard/summary
GET /api/v1/cost-records
GET /api/v1/audit-events
GET /api/v1/notifications
PATCH /api/v1/notifications/{id}/read
```

## Contrat provisioning Terraform

Le backend ne lance pas Terraform directement.

Le futur service de provisioning doit :

1. appeler `POST /api/v1/vm-requests/{id}/provision`;
2. executer Terraform/OpenTofu;
3. renvoyer le resultat via `PATCH /api/v1/virtual-machines/{id}/provisioning-result`;
4. renvoyer la destruction via `PATCH /api/v1/virtual-machines/{id}/destruction-result`.
