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
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

Documentation API :

```text
http://localhost:3000/docs
```

## Mode auth

Le backend supporte un mode de developpement `AUTH_MODE=mock`.

L'integration OIDC Microsoft Entra ID reelle est preparee au niveau configuration, mais elle depend des acces tenant fournis par le GIT.

## Frontiere infrastructure

Le backend ne lance aucune commande Terraform, OpenTofu, SSH ou Ansible.

Il expose des endpoints propres pour que la partie infra puisse s'integrer ensuite :

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
