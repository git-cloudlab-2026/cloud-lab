import asyncio
import json
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.domain.enums import AuditSeverity, RequestStatus, VmStatus
from app.domain.models import AuditEvent, User, VirtualMachine, VmRequest


def normalize_status(value: str | None) -> VmStatus:
    normalized = (value or VmStatus.running.value).lower()
    if normalized in {"active", "up"}:
        return VmStatus.running
    if normalized in {"shutoff", "stopped"}:
        return VmStatus.stopped
    if normalized in {"error", "failed"}:
        return VmStatus.error
    return VmStatus(normalized)


def env_int(name: str) -> int:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} est obligatoire.")
    return int(value)


def read_outputs() -> dict[str, dict[str, Any]]:
    output_file = os.getenv("SYNC_TERRAFORM_OUTPUT_FILE")
    if output_file:
        data = json.loads(Path(output_file).read_text(encoding="utf-8-sig"))
    else:
        terraform_dir = Path(os.getenv("SYNC_TERRAFORM_DIR", ".")).expanduser().resolve()
        terraform_binary = os.getenv("TERRAFORM_BINARY", "terraform")
        process = subprocess.run(
            [terraform_binary, "output", "-json", "provisioning_results"],
            cwd=terraform_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(process.stdout)

    if "value" in data and isinstance(data["value"], dict):
        data = data["value"]
    if not isinstance(data, dict):
        raise RuntimeError("La sortie provisioning_results est invalide.")
    return data


async def main() -> None:
    request_id = env_int("SYNC_TERRAFORM_REQUEST_ID")
    owner_id = env_int("SYNC_TERRAFORM_OWNER_ID")
    start_date = date.fromisoformat(os.getenv("SYNC_TERRAFORM_START_DATE", date.today().isoformat()))
    end_date = date.fromisoformat(os.getenv("SYNC_TERRAFORM_END_DATE", start_date.isoformat()))
    ssh_username = os.getenv("SYNC_TERRAFORM_SSH_USERNAME", "student")
    ssh_fingerprint = os.getenv("SYNC_TERRAFORM_SSH_FINGERPRINT")

    outputs = read_outputs()

    async with SessionLocal() as session:
        request = await session.get(VmRequest, request_id)
        owner = await session.get(User, owner_id)
        if not request:
            raise RuntimeError(f"Demande VM #{request_id} introuvable.")
        if not owner:
            raise RuntimeError(f"Utilisateur #{owner_id} introuvable.")

        created = 0
        updated = 0
        for name, item in outputs.items():
            provider_vm_id = item.get("provider_vm_id")
            if not provider_vm_id:
                continue

            existing = await session.scalar(
                select(VirtualMachine).where(VirtualMachine.provider_vm_id == provider_vm_id)
            )
            if existing:
                vm = existing
                updated += 1
            else:
                vm = VirtualMachine(
                    request_id=request.id,
                    owner_id=owner.id,
                    provider_vm_id=provider_vm_id,
                    name=name,
                    status=VmStatus.running,
                    ssh_username=ssh_username,
                    start_date=start_date,
                    end_date=end_date,
                )
                session.add(vm)
                created += 1

            vm.name = name
            vm.ip_address = item.get("ip_address")
            vm.network_segment = item.get("network_segment")
            vm.status = normalize_status(item.get("status"))
            vm.ssh_key_fingerprint = ssh_fingerprint

        request.status = RequestStatus.provisioned
        session.add(
            AuditEvent(
                actor_id=None,
                request_id=request.id,
                event_type="terraform_outputs_synced",
                severity=AuditSeverity.success,
                event_message=f"Outputs Terraform synchronises: {created} creee(s), {updated} mise(s) a jour.",
            )
        )
        await session.commit()

    print(f"Synchronisation Terraform terminee: {created} creee(s), {updated} mise(s) a jour.")


if __name__ == "__main__":
    asyncio.run(main())
