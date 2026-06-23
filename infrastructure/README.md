# Terraform - Cloud Lab Control Center (OpenStack / Infomaniak)

Infra complete pour le provisioning des VM pedagogiques : reseau, securite, VM.
Ce module ne touche pas au backend FastAPI ; il produit en sortie exactement
ce que le backend attend via `PATCH /api/v1/virtual-machines/{id}/provisioning-result`.

## Contenu

```text
versions.tf              Provider OpenStack (~> 1.53), auth via clouds.yaml
variables.tf              Toutes les variables (region, reseau, VM, SSH...)
network.tf                Network + subnet + router + interface vers ext-net
security.tf                Security group (SSH restreint, ICMP interne, egress libre) + keypair
compute.tf                  Instances + floating IP optionnelle
outputs.tf                 provisioning_results au format attendu par le backend
terraform.tfvars.example   Exemple de variables sans secret
clouds.yaml.example         Exemple d'auth OpenStack sans secret
```

## Prerequis

- Terraform >= 1.6
- Acces OpenStack Infomaniak valides
- Un `clouds.yaml` reel (copie de `clouds.yaml.example`), **jamais commit**

## Authentification

```powershell
copy clouds.yaml.example clouds.yaml
# editer clouds.yaml avec les vrais identifiants Infomaniak
```

Terraform lit `clouds.yaml` automatiquement (repertoire courant, puis
`~/.config/openstack/clouds.yaml`).

## Utilisation

```powershell
copy terraform.tfvars.example terraform.tfvars
# editer terraform.tfvars : cle SSH publique, liste des VM a creer

terraform init
terraform plan
terraform apply
```

## Recuperer les resultats pour le backend

```powershell
terraform output -json provisioning_results
```

Chaque entree correspond a une VM et contient `provider_vm_id`, `ip_address`,
`status`, `network_segment` — directement utilisable pour appeler :

```http
PATCH /api/v1/virtual-machines/{id}/provisioning-result
```

## Destruction (fin de vie)

```powershell
terraform destroy
```

Le statut `destroyed` cote backend doit ensuite etre rapporte via :

```http
PATCH /api/v1/virtual-machines/{id}/destruction-result
```

## Securite

- Jamais commit : `clouds.yaml`, `*.tfvars` (hors `.example`), `*.tfstate`, `.terraform/`.
- `allowed_ssh_cidrs` doit etre resserre en dehors du `0.0.0.0/0` de demo.
- Un security group isole par segment (`network_segment`) limite la portee
  d'une classe a l'autre (E1 a E5).
