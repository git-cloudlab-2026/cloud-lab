from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services.mock_terraform import MockTerraformService


@pytest.mark.asyncio
async def test_mock_terraform_create_vm_returns_realistic_contract():
    today = date.today()
    request = SimpleNamespace(id=12, start_date=today, end_date=today + timedelta(days=3))
    template = SimpleNamespace(name="Administration Linux")
    owner = SimpleNamespace(email="etudiant1@giptech.ch", role=SimpleNamespace(value="student"), class_name="E1")

    result = await MockTerraformService().create_vm(request, template, owner)

    assert result.provider_vm_id.startswith("mock-openstack-")
    assert result.name.startswith("git-administration-linux-")
    assert result.ip_address.startswith("10.42.")
    assert result.network_segment == "class-e1"
    assert result.ssh_username == "student"


@pytest.mark.asyncio
async def test_mock_terraform_destroy_vm_returns_true():
    assert await MockTerraformService().destroy_vm("mock-openstack-0001-01") is True
