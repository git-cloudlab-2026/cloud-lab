import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import ApiError
from app.domain.models import User, VmRequest, VmTemplate

logger = logging.getLogger(__name__)

# Fichiers du module infrastructure à NE PAS copier dans le run_dir isolé.
# FIX Bug 6: on exclut terraform.tfstate et terraform.tfstate.backup pour ne pas
# corrompre l'état de chaque provisionnement avec l'état de l'infra principale.
_SKIP_FILES = {
    ".terraform",
    "terraform.tfstate",
    "terraform.tfstate.backup",
    ".terraform.lock.hcl",
    "cloud-lab-key",          # clé privée SSH — ne pas copier dans les runs
}


@dataclass(frozen=True)
class TerraformVm:
    provider_vm_id: str
    name: str
    ip_address: str | None
    ssh_username: str
    ssh_key_fingerprint: str | None
    network_segment: str


class TerraformService:
    """Provisionne les VMs avec le module Terraform/OpenTofu du projet."""

    async def create_vms(self, request: VmRequest, template: VmTemplate, owner: User) -> list[TerraformVm]:
        settings = get_settings()
        module_dir = self._module_dir()
        run_dir = self._run_dir(request.id)
        await asyncio.to_thread(self._prepare_run_dir, module_dir, run_dir)

        vm_requests = [
            {
                "name": self._vm_name(request, template, index),
                "class_tag": owner.class_name or "staff",
                "owner_email": owner.email,
            }
            for index in range(1, request.quantity + 1)
        ]
        tfvars = {
            "openstack_cloud_name": settings.terraform_openstack_cloud_name,
            "region": settings.terraform_region,
            "project_prefix": settings.terraform_project_prefix,
            "network_segment": self._network_segment(owner),
            "network_cidr": self._network_cidr(owner),
            "external_network_name": settings.terraform_external_network_name,
            "allowed_ssh_cidrs": settings.terraform_allowed_ssh_cidrs,
            "ssh_keypair_name": settings.openstack_keypair_name,
            "assign_floating_ip": settings.terraform_assign_floating_ip,
            "vm_requests": vm_requests,
        }
        if settings.terraform_default_flavor_name:
            tfvars["default_flavor_name"] = settings.terraform_default_flavor_name
        if settings.terraform_image_name:
            tfvars["image_name"] = settings.terraform_image_name

        await asyncio.to_thread(
            (run_dir / "terraform.auto.tfvars.json").write_text,
            json.dumps(tfvars, indent=2),
            "utf-8",
        )

        logger.info("Terraform provisioning start request=%s run_dir=%s", request.id, run_dir)
        await self._run_command([settings.terraform_binary, "init", "-input=false"], run_dir)
        await self._run_command([settings.terraform_binary, "apply", "-auto-approve", "-input=false"], run_dir)
        output = await self._run_command(
            [settings.terraform_binary, "output", "-json", "provisioning_results"],
            run_dir,
            capture_output=True,
        )
        results = self._parse_output(output)
        fingerprint = await self._ssh_fingerprint(run_dir)

        await asyncio.to_thread(
            (run_dir / "provisioning_results.json").write_text,
            json.dumps(results, indent=2),
            "utf-8",
        )

        return [
            TerraformVm(
                provider_vm_id=item["provider_vm_id"],
                name=name,
                ip_address=item.get("ip_address"),
                ssh_username="student" if owner.role.value == "student" else "trainer",
                ssh_key_fingerprint=fingerprint,
                network_segment=item.get("network_segment") or self._network_segment(owner),
            )
            for name, item in results.items()
        ]

    async def create_vm(self, request: VmRequest, template: VmTemplate, owner: User, index: int = 1) -> TerraformVm:
        vms = await self.create_vms(request, template, owner)
        if index < 1 or index > len(vms):
            raise ApiError(500, "terraform_vm_missing", f"Terraform n'a pas retourne la VM index {index}.")
        return vms[index - 1]

    async def destroy_vm(self, provider_vm_id: str | None) -> bool:
        if not provider_vm_id:
            return False
        settings = get_settings()
        run_dir = await asyncio.to_thread(self._find_run_dir_for_provider_id, provider_vm_id)
        if not run_dir:
            raise ApiError(
                404,
                "terraform_state_not_found",
                "Aucun etat Terraform local ne correspond a cette VM.",
            )
        logger.info("Terraform destroy start provider_vm_id=%s run_dir=%s", provider_vm_id, run_dir)
        await self._run_command([settings.terraform_binary, "destroy", "-auto-approve", "-input=false"], run_dir)
        return True

    def _module_dir(self) -> Path:
        settings = get_settings()
        if settings.terraform_module_dir:
            configured = Path(settings.terraform_module_dir).expanduser()
            resolved = configured.resolve()
            if resolved.exists() or configured.is_absolute():
                return resolved
            return (Path(__file__).resolve().parents[3] / configured).resolve()
        # FIX Bug 1: résolution depuis le projet quand pas de chemin configuré
        return Path(__file__).resolve().parents[3] / "infrastructure"

    def _run_dir(self, request_id: int) -> Path:
        settings = get_settings()
        root = Path(settings.terraform_work_dir).expanduser()
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[3] / root
        return root.resolve() / f"request-{request_id:04d}"

    def _prepare_run_dir(self, module_dir: Path, run_dir: Path) -> None:
        if not module_dir.exists():
            raise ApiError(500, "terraform_module_missing", f"Module Terraform introuvable: {module_dir}")
        run_dir.mkdir(parents=True, exist_ok=True)

        for source in module_dir.iterdir():
            # FIX Bug 6: exclut tfstate et clés privées pour isoler chaque run
            if source.name in _SKIP_FILES:
                continue
            target = run_dir / source.name
            if source.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)

        # FIX Bug 8: valide clouds.yaml dans le run_dir APRÈS copie, pas avant.
        # S'il n'est pas dans module_dir, il doit être fourni séparément dans run_dir.
        clouds_file = run_dir / "clouds.yaml"
        if not clouds_file.exists():
            raise ApiError(
                500,
                "terraform_clouds_yaml_missing",
                (
                    f"Fichier clouds.yaml introuvable dans {run_dir}. "
                    "Copie infrastructure/clouds.yaml avec tes credentials Infomaniak. "
                    "Consulte infrastructure/clouds.yaml.example."
                ),
            )

    def _network_segment(self, owner: User) -> str:
        return f"class-{(owner.class_name or 'staff').lower()}"

    def _network_cidr(self, owner: User) -> str:
        settings = get_settings()
        class_name = (owner.class_name or "staff").upper()
        if class_name.startswith("E") and class_name[1:].isdigit():
            return f"10.42.{int(class_name[1:])}.0/24"
        return settings.terraform_network_cidr

    def _vm_name(self, request: VmRequest, template: VmTemplate, index: int) -> str:
        slug = "".join(ch if ch.isalnum() else "-" for ch in template.name.lower()).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return f"git-{slug}-{request.id:04d}-{index:02d}"

    async def _ssh_fingerprint(self, run_dir: Path) -> str | None:
        settings = get_settings()
        try:
            raw = await self._run_command(
                [settings.terraform_binary, "output", "-raw", "ssh_fingerprint"],
                run_dir,
                capture_output=True,
            )
            return raw.strip() or None
        except ApiError:
            return None

    async def _run_command(self, command: list[str], cwd: Path, capture_output: bool = False) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode(errors="replace")
        stderr_text = stderr.decode(errors="replace")
        if process.returncode != 0:
            logger.error("Terraform command failed: %s\n%s", " ".join(command), stderr_text)
            raise ApiError(
                500,
                "terraform_command_failed",
                f"Commande Terraform echouee: {' '.join(command)}\n{stderr_text[-1200:]}",
            )
        if stderr_text:
            logger.info("Terraform stderr: %s", stderr_text)
        return stdout_text if capture_output else ""

    def _parse_output(self, output: str) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(output)
        except json.JSONDecodeError as exc:
            raise ApiError(500, "terraform_output_invalid", "Sortie Terraform JSON invalide.") from exc
        if "value" in data and isinstance(data["value"], dict):
            data = data["value"]
        if not isinstance(data, dict):
            raise ApiError(500, "terraform_output_invalid", "Sortie provisioning_results inattendue.")
        return data

    def _find_run_dir_for_provider_id(self, provider_vm_id: str) -> Path | None:
        settings = get_settings()
        root = Path(settings.terraform_work_dir).expanduser()
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[3] / root
        if not root.exists():
            return None
        for result_file in root.glob("request-*/provisioning_results.json"):
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for item in data.values():
                if item.get("provider_vm_id") == provider_vm_id:
                    return result_file.parent
        return None
