# Relier Terraform, Infomaniak et le site

Cette page explique le lien entre :

```text
Terraform de Rayan -> Infomaniak OpenStack -> Backend FastAPI -> Dashboard web
```

## Etat confirme

Les captures Infomaniak/Terraform montrent une VM reelle :

```text
instance_name   = cloud-lab-e1-eleve01-vm / e1-eleve01-vm
provider_vm_id  = 38ce4499-c909-454e-a624-fc437d2380ab
ip_address      = 10.42.0.70
network_segment = IT-2026-A
status          = running
image           = Ubuntu 24.04 LTS Noble Numbat
flavor          = a1-ram2-disk20-perf1
key_pair        = cloud-lab-key
region          = dc4-a
project         = PCP-B8MJTY2
```

Terraform indique aussi :

```text
No changes. Your infrastructure matches the configuration.
Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
```

Donc Terraform est deja bien relie a Infomaniak. Le travail cote site consiste a
mettre ces resultats dans la base du backend.

## 1. Synchroniser la VM deja creee

Depuis le projet backend :

```powershell
cd server

$env:SYNC_TERRAFORM_DIR="C:\Users\zaghe\Downloads\cloud-lab-terraform"
$env:SYNC_TERRAFORM_REQUEST_ID="1"
$env:SYNC_TERRAFORM_OWNER_ID="100"
$env:SYNC_TERRAFORM_START_DATE="2026-06-23"
$env:SYNC_TERRAFORM_END_DATE="2026-06-30"
$env:SYNC_TERRAFORM_SSH_USERNAME="student"
$env:SYNC_TERRAFORM_SSH_FINGERPRINT="21:a2:f0:3c:86:82:a5:c6:c0:ef:25:fa:a3:f3:2c:eb"

python -m scripts.sync_terraform_outputs
```

Le script lance :

```powershell
terraform output -json provisioning_results
```

puis cree ou met a jour les lignes `virtual_machines` dans PostgreSQL.

Apres ca, le dashboard peut recuperer la VM via :

```http
GET /api/v1/virtual-machines
```

## 2. Activer le provisioning depuis le site

Pour que la validation d'une demande lance Terraform automatiquement :

```env
PROVISIONER_MODE=terraform
TERRAFORM_BINARY=terraform
TERRAFORM_MODULE_DIR=./infrastructure
TERRAFORM_WORK_DIR=.terraform-runs
TERRAFORM_OPENSTACK_CLOUD_NAME=openstack
TERRAFORM_REGION=dc4-a
TERRAFORM_PROJECT_PREFIX=cloud-lab
TERRAFORM_EXTERNAL_NETWORK_NAME=ext-floating1
TERRAFORM_SSH_PUBLIC_KEY_PATH=~/.ssh/id_ed25519.pub
```

Ensuite le workflow devient :

```text
POST /api/v1/vm-requests/{id}/approve
-> backend
-> TerraformService
-> terraform init/apply/output
-> creation des VMs en base
-> affichage dans le portail
```

## Attention production

Le dossier Terraform de Rayan contient probablement un etat local. Ne pas
ecraser ses fichiers `terraform.tfvars` ou `terraform.tfstate` sans accord.

Pour une vraie production, le mieux est :

- soit un backend Terraform remote state;
- soit un dossier de run par demande;
- soit un job de provisioning dedie, appele par le backend.

Le code actuel supporte le mode demo `mock`, le mode reel `terraform`, et une
synchronisation des outputs Terraform deja existants.
