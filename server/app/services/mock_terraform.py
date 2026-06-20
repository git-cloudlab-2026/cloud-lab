import asyncio
import logging
import random
from dataclasses import dataclass

from app.core.config import get_settings
from app.domain.models import User, VmTemplate, VmRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MockTerraformVm:
    provider_vm_id: str
    name: str
    ip_address: str
    ssh_username: str
    ssh_key_fingerprint: str
    network_segment: str


class MockTerraformService:
    """Simule le contrat Terraform/OpenTofu sans toucher a une vraie infra."""

    async def create_vm(self, request: VmRequest, template: VmTemplate, owner: User, index: int = 1) -> MockTerraformVm:
        settings = get_settings()
        logger.info("Mock Terraform: plan request=%s template=%s owner=%s", request.id, template.name, owner.email)
        await asyncio.sleep(settings.mock_terraform_create_delay_seconds)

        class_segment = (owner.class_name or "staff").lower()
        suffix = f"{request.id:04d}-{index:02d}"
        return MockTerraformVm(
            provider_vm_id=f"mock-openstack-{suffix}",
            name=f"git-{template.name.lower().replace(' ', '-')}-{suffix}",
            ip_address=f"10.42.{request.id % 250}.{20 + index}",
            ssh_username="student" if owner.role.value == "student" else "trainer",
            ssh_key_fingerprint=f"SHA256:mock-{request.id}-{index}-{random.randint(1000, 9999)}",
            network_segment=f"class-{class_segment}",
        )

    async def destroy_vm(self, provider_vm_id: str | None) -> bool:
        settings = get_settings()
        logger.info("Mock Terraform: destroy provider_vm_id=%s", provider_vm_id or "unknown")
        await asyncio.sleep(settings.mock_terraform_destroy_delay_seconds)
        return True
