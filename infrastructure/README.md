# Infrastructure Terraform / OpenTofu

Ce dossier contient le point de depart Infrastructure as Code pour Infomaniak Public Cloud via OpenStack.

## Ressources creees

- reseau prive OpenStack;
- sous-reseau IPv4;
- routeur connecte au reseau externe;
- security group SSH + ICMP;
- paire de cles SSH;
- une ou plusieurs VMs Ubuntu;
- floating IPs optionnelles;
- outputs VM ID, IPs et commandes SSH.

## Configuration

Copier le fichier exemple :

```powershell
cd infrastructure
Copy-Item terraform.tfvars.example terraform.tfvars
```

Puis remplir `terraform.tfvars` avec les valeurs du projet Infomaniak/OpenStack.

Ne jamais commit `terraform.tfvars`, `*.tfstate`, cle SSH privee ou fichier OpenRC.

## Cle SSH

Terraform doit envoyer une cle publique a OpenStack pour permettre l'acces SSH aux VMs.

Si aucune cle n'existe encore sur Windows :

```powershell
ssh-keygen -t ed25519 -C "cloud-lab"
```

Accepter le chemin propose par defaut :

```text
C:\Users\<votre-utilisateur>\.ssh\id_ed25519
```

Puis garder dans `terraform.tfvars` :

```hcl
ssh_public_key_path = "~/.ssh/id_ed25519.pub"
```

Si vous utilisez une autre cle, renseigner le chemin complet du fichier `.pub`.

## Commandes

```powershell
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
terraform output
```

Destruction complete :

```powershell
terraform destroy
```

## Integration future backend

Le backend ne lance pas Terraform directement. Le contrat propre est :

1. le portail approuve une demande;
2. un job/provisioner externe lance Terraform;
3. Terraform retourne `vm_id`, `ip_address`, `name`;
4. le provisioner appelle l'API backend pour enregistrer le resultat.

Endpoints backend utiles :

- `POST /api/v1/vm-requests/{id}/provision`
- `PATCH /api/v1/virtual-machines/{id}/provisioning-result`
- `PATCH /api/v1/virtual-machines/{id}/destruction-result`
