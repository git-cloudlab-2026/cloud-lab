# Cloud Lab Control Center

Projet hackathon juin 2026 - Geneva Institute of Technology x Satom IT.

## Objectif du projet

Créer une plateforme de gestion du cycle de vie des VM de cours :

```text
Demande -> Validation -> Provisioning -> Configuration -> Monitoring -> Destruction
```

Le but est de permettre à un étudiant ou un formateur de demander une VM de cours, de faire valider cette demande, puis de suivre la machine, son statut, son coût et sa date de fin.

## Contenu actuel du dépôt

Ce premier push contient uniquement la partie réalisée par Auguy :

- portail MVP en HTML/CSS/JavaScript ;
- catalogue de templates VM ;
- formulaire de demande ;
- validation/refus ;
- simulation du provisioning ;
- suivi des VM ;
- dashboard ;
- calcul des coûts estimés et réels ;
- alertes d'expiration ;
- exports CSV ;
- schéma data et requêtes SQL.

Les parties Terraform/OpenTofu, réseau/sécurité et Ansible seront ajoutées ensuite par les autres membres du groupe.

## Répartition actuelle

| Personne | Partie |
|---|---|
| Auguy | Portail MVP, workflow, data, dashboard, coûts, exports |
| Josué | Terraform/OpenTofu, création et destruction des VM |
| Lorenzo | Réseau, sécurité, SSH, isolation OpenStack |

Rayan n'est plus dans le périmètre du projet.

## Structure actuelle

```text
app/        portail MVP local
data/       schéma SQL, seed data, requêtes dashboard
README.md   présentation du projet
.gitignore  fichiers à exclure du dépôt
.env.example exemple de variables d'environnement
```

## Ouvrir la démo locale

Le portail fonctionne sans serveur.

Ouvrir ce fichier dans un navigateur :

```text
app/index.html
```

## Ce que montre la démo

1. Vue dashboard avec KPI principaux.
2. Catalogue des templates de cours.
3. Création d'une demande VM.
4. Validation ou refus d'une demande.
5. Simulation de provisioning.
6. Parc VM avec statut, réseau, date de fin et coût réel.
7. Budget par cours.
8. Alertes VM expirées ou proches de l'expiration.
9. Exports CSV des demandes et des VM.

## Modèle de coût

Les coûts ne sont pas mis au hasard.

Le MVP utilise une référence publique Infomaniak Public Cloud :

```text
4 CPU / 8 GB RAM / 50 GB stockage = 16.10 CHF/mois
```

Le prix est ensuite proratisé selon CPU, RAM, disque et durée d'utilisation.

Le portail distingue :

- coût estimé : calculé au moment de la demande ;
- coût réel : calculé selon la durée réelle d'utilisation de la VM.

## Prochaines intégrations

### Josué - Terraform/OpenTofu

À ajouter ensuite :

- lecture des demandes `approved` ;
- création VM Infomaniak OpenStack ;
- retour de l'ID fournisseur, IP, statut ;
- destruction des VM expirées.

### Lorenzo - Réseau/Sécurité

À ajouter ensuite :

- segments réseau par cours ou classe ;
- règles firewall ;
- accès SSH par clés ;
- isolation des environnements sensibles.

## Sécurité

Ne jamais commit :

- fichiers `.env` réels ;
- tokens ;
- mots de passe OpenStack ;
- fichiers `clouds.yaml` avec secrets ;
- clés SSH privées ;
- fichiers Terraform `*.tfstate` ou `*.tfvars`.

