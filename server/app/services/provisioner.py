from app.core.config import get_settings
from app.core.errors import ApiError
from app.services.mock_terraform import MockTerraformService
from app.services.openstack_service import OpenStackService
from app.services.terraform_service import TerraformService


def get_provisioner():
    settings = get_settings()
    if settings.provisioner_mode in {"terraform", "openstack"} and not settings.real_provisioning_enabled:
        raise ApiError(
            409,
            "real_provisioning_disabled",
            "Provisionnement reel desactive. Mets REAL_PROVISIONING_ENABLED=true pour autoriser la creation Infomaniak.",
        )
    if settings.provisioner_mode == "openstack":
        return OpenStackService()
    if settings.provisioner_mode == "terraform":
        return TerraformService()
    return MockTerraformService()
