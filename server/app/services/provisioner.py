import logging

from app.core.config import get_settings
from app.services.mock_terraform import MockTerraformService
from app.services.openstack_service import OpenStackService
from app.services.terraform_service import TerraformService

logger = logging.getLogger(__name__)


def get_provisioner():
    """Retourne le provisioner actif selon PROVISIONER_MODE et REAL_PROVISIONING_ENABLED.

    FIX Bug 3 — l'ancien code levait ApiError(409) à l'instanciation du service si
    PROVISIONER_MODE=terraform et REAL_PROVISIONING_ENABLED=false. Cela cassait TOUTES
    les routes VM (même lister les demandes) parce que VmRequestService appelle
    get_provisioner() dans son __init__.

    Nouveau comportement :
    - PROVISIONER_MODE=mock → MockTerraformService (jamais de vraie ressource)
    - PROVISIONER_MODE=terraform/openstack + REAL_PROVISIONING_ENABLED=true → vrai provisioner
    - PROVISIONER_MODE=terraform/openstack + REAL_PROVISIONING_ENABLED=false → MockTerraformService
      avec avertissement dans les logs (sécurité : on ne crée rien sur Infomaniak par accident)

    Pour activer le provisionnement réel Infomaniak, mets dans .env :
        PROVISIONER_MODE=terraform
        REAL_PROVISIONING_ENABLED=true
    """
    settings = get_settings()

    if settings.provisioner_mode in {"terraform", "openstack"} and not settings.real_provisioning_enabled:
        logger.warning(
            "PROVISIONER_MODE=%s mais REAL_PROVISIONING_ENABLED=false → "
            "MockTerraformService utilisé. Aucune ressource Infomaniak ne sera créée. "
            "Mets REAL_PROVISIONING_ENABLED=true pour provisionner réellement.",
            settings.provisioner_mode,
        )
        return MockTerraformService()

    if settings.provisioner_mode == "openstack":
        return OpenStackService()
    if settings.provisioner_mode == "terraform":
        return TerraformService()
    return MockTerraformService()
