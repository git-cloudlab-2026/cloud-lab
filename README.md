# Cloud Lab Control Center

Projet hackathon juin 2026 - Geneva Institute of Technology x Satom IT.

## Objectif

Construire une plateforme de gestion du cycle de vie des VM de cours :

```text
Demande -> Validation -> Provisioning -> Configuration -> Monitoring -> Fin de vie
```

Le portail permet a un etudiant ou un formateur de demander une VM, de faire valider la demande, puis de suivre la machine, son statut, son cout et sa date de fin.

## Etat actuel du depot

Ce depot contient la partie deja avancee par Auguy :

- portail front-end statique dans `app/`;
- couche data documentee dans `data/`;
- backend FastAPI + PostgreSQL dans `server/`;
- schema SQL, seed data, migrations Alembic;
- API REST versionnee `/api/v1`;
- workflow demande, validation, provisioning intent, fin de vie;
- dashboard, couts, alertes, notifications, audit;
- auth OIDC/Entra ID avec mapping groupes vers roles;
- 5 classes E1 a E5 avec 25 eleves par classe dans le seed backend;
- points d'integration prepares pour Terraform/OpenTofu et monitoring.

Les parties Terraform/OpenTofu, reseau/securite et Ansible restent separees pour eviter de melanger les responsabilites.

## Repartition actuelle

| Personne | Perimetre |
|---|---|
| Auguy | Portail, data, backend API, dashboard, couts, audit, notifications |
| Josue | Terraform/OpenTofu, creation et destruction reelle des VM |
| Lorenzo | Reseau, securite, SSH, isolation OpenStack |

Rayan n'est plus dans le perimetre actif du projet.

## Structure

```text
app/                 Front-end statique HTML/CSS/JS
data/                Schema SQL de reference, seed et requetes dashboard
server/              Backend FastAPI + PostgreSQL
docker-compose.yml   PostgreSQL + API pour le dev local
.env.example         Variables d'environnement sans secret
.gitignore           Fichiers exclus du depot
```

## Lancer le front-end

Le portail statique peut etre ouvert directement :

```text
app/index.html
```

## Lancer le backend FastAPI

Avec Docker :

```powershell
docker compose up --build
```

En local :

> Utiliser Python 3.12. Python 3.14 peut poser probleme avec certaines dependances PostgreSQL.

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentation API :

```text
http://localhost:8000/docs
```

Portail web branche sur FastAPI :

```text
http://localhost:8000/portal/
```

Pour tester l'application avec sessions et cookies, utiliser cette URL plutot que
`app/index.html` en `file://`.

## Mode auth

Le backend supporte un mode de developpement `AUTH_MODE=mock`.

L'integration OIDC Microsoft Entra ID reelle est preparee au niveau configuration.

En attendant les acces Microsoft Entra ID du GIT, le backend expose aussi une
authentification JWT locale pour tester l'API comme un vrai client externe.

Comptes JWT de demonstration :

| Email | Mot de passe | Role |
|---|---|---|
| `admin@giptech.ch` | `admin123` | `admin` |
| `prof@giptech.ch` | `prof123` | `teacher` |
| `etudiant1@giptech.ch` | `etu123` | `student` |

Exemple :

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@giptech.ch",
  "password": "admin123"
}
```

La reponse contient un `access_token` JWT a envoyer ensuite avec :

```http
Authorization: Bearer <token>
```

Mapping prevu :

```text
Admin / Validateurs / Enseignants / E1 / E2 / E3 / E4 / E5
```

Les etudiants peuvent etre crees automatiquement au premier login si leur groupe Entra indique leur classe. Les roles sensibles restent controles par la base applicative.

## Frontiere infrastructure

Le backend ne lance aucune commande Terraform, OpenTofu, SSH ou Ansible.

Pour travailler sans acces OpenStack, il contient un `MockTerraformService` qui
simule la creation/destruction et retourne des donnees realistes :

- id provider mock;
- nom de VM;
- adresse IP privee;
- segment reseau;
- fingerprint SSH.

Routes utiles pour tester le cycle complet :

- `POST /api/v1/vm-requests/{id}/approve` : approuve et provisionne en mock;
- `POST /api/v1/vm-requests/{id}/reject` : refuse une demande;
- `GET /api/v1/virtual-machines/{id}` : detail d'une VM visible par l'utilisateur;
- `POST /api/v1/virtual-machines/{id}/destroy` : destruction mock + audit + notification;
- `GET /api/v1/virtual-machines/expired` : VMs expirees a traiter.

Il expose aussi des endpoints propres pour que la partie infra reelle puisse
s'integrer ensuite :

- `POST /api/v1/vm-requests/{id}/provision`
- `PATCH /api/v1/virtual-machines/{id}/provisioning-result`
- `PATCH /api/v1/virtual-machines/{id}/destruction-result`

## Securite

Ne jamais commit :

- `.env` reel;
- token, mot de passe ou secret OpenStack;
- fichier `clouds.yaml` contenant des secrets;
- cle SSH privee;
- fichiers Terraform `*.tfstate` ou `*.tfvars`.
