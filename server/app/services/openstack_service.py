import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import ApiError
from app.domain.models import User, VmRequest, VmTemplate


@dataclass(frozen=True)
class OpenStackVm:
    provider_vm_id: str
    name: str
    ip_address: str | None
    ssh_username: str
    ssh_key_fingerprint: str | None
    network_segment: str


class OpenStackService:
    """Provisionne directement une VM via les APIs OpenStack Infomaniak."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def create_vms(self, request: VmRequest, template: VmTemplate, owner: User) -> list[OpenStackVm]:
        self._validate_create_settings()
        async with httpx.AsyncClient(timeout=60) as client:
            token, catalog = await self._authenticate(client)
            compute_url = self._endpoint(catalog, "compute")
            image_url = self._versioned_url(self._endpoint(catalog, "image"), "v2")
            network_url = self._versioned_url(self._endpoint(catalog, "network"), "v2.0")

            image_id = await self._find_image_id(client, token, image_url, self.settings.terraform_image_name)
            flavor_id = await self._find_flavor_id(client, token, compute_url, self.settings.terraform_default_flavor_name)
            network_id = await self._resolve_network_id(client, token, network_url)

            created: list[OpenStackVm] = []
            for index in range(1, request.quantity + 1):
                name = self._vm_name(request, template, index)
                server = await self._create_server(
                    client,
                    token,
                    compute_url,
                    name=name,
                    image_id=image_id,
                    flavor_id=flavor_id,
                    network_id=network_id,
                )
                server = await self._wait_for_server(client, token, compute_url, server["id"])
                ip_address = self._first_private_ip(server)
                if self.settings.terraform_assign_floating_ip:
                    ip_address = await self._assign_floating_ip(client, token, network_url, server["id"])
                created.append(
                    OpenStackVm(
                        provider_vm_id=server["id"],
                        name=server.get("name") or name,
                        ip_address=ip_address,
                        ssh_username="student" if owner.role.value == "student" else "trainer",
                        ssh_key_fingerprint=self.settings.openstack_keypair_name,
                        network_segment=self._network_segment(owner),
                    )
                )
            return created

    async def create_vm(self, request: VmRequest, template: VmTemplate, owner: User, index: int = 1) -> OpenStackVm:
        vms = await self.create_vms(request, template, owner)
        if index < 1 or index > len(vms):
            raise ApiError(500, "openstack_vm_missing", f"OpenStack n'a pas retourne la VM index {index}.")
        return vms[index - 1]

    async def destroy_vm(self, provider_vm_id: str | None) -> bool:
        if not provider_vm_id:
            return False
        self._validate_auth_settings()
        async with httpx.AsyncClient(timeout=60) as client:
            token, catalog = await self._authenticate(client)
            compute_url = self._endpoint(catalog, "compute")
            response = await client.delete(f"{compute_url}/servers/{provider_vm_id}", headers={"X-Auth-Token": token})
            if response.status_code not in {202, 204, 404}:
                raise ApiError(500, "openstack_delete_failed", self._error_message(response))
            return True

    def _validate_auth_settings(self) -> None:
        missing = [
            name
            for name, value in {
                "OS_AUTH_URL": self.settings.os_auth_url,
                "OS_PROJECT_NAME": self.settings.os_project_name,
                "OS_USERNAME": self.settings.os_username,
                "OS_PASSWORD": self.settings.os_password,
            }.items()
            if not value
        ]
        if missing:
            raise ApiError(500, "openstack_config_missing", f"Configuration OpenStack incomplete: {', '.join(missing)}.")

    def _validate_create_settings(self) -> None:
        self._validate_auth_settings()
        if not (self.settings.openstack_network_id or self.settings.openstack_network_name):
            raise ApiError(500, "openstack_network_missing", "Configure OPENSTACK_NETWORK_ID ou OPENSTACK_NETWORK_NAME.")
        if not self.settings.openstack_keypair_name:
            raise ApiError(500, "openstack_keypair_missing", "Configure OPENSTACK_KEYPAIR_NAME.")

    async def _authenticate(self, client: httpx.AsyncClient) -> tuple[str, list[dict[str, Any]]]:
        auth_url = self.settings.os_auth_url.rstrip("/")
        if not auth_url.endswith("/v3"):
            auth_url = f"{auth_url}/v3"
        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": self.settings.os_username,
                            "domain": {"name": self.settings.os_user_domain_name},
                            "password": self.settings.os_password,
                        }
                    },
                },
                "scope": {
                    "project": {
                        "name": self.settings.os_project_name,
                        "domain": {"name": self.settings.os_project_domain_name},
                    }
                },
            }
        }
        response = await client.post(f"{auth_url}/auth/tokens", json=payload)
        if response.status_code != 201:
            raise ApiError(401, "openstack_auth_failed", self._error_message(response))
        return response.headers["X-Subject-Token"], response.json()["token"]["catalog"]

    def _endpoint(self, catalog: list[dict[str, Any]], service_type: str) -> str:
        for service in catalog:
            if service.get("type") != service_type:
                continue
            endpoints = [
                endpoint
                for endpoint in service.get("endpoints", [])
                if endpoint.get("interface") == "public"
                and endpoint.get("region") in {self.settings.os_region_name, None}
            ]
            if endpoints:
                return endpoints[0]["url"].rstrip("/")
        raise ApiError(500, "openstack_endpoint_missing", f"Endpoint OpenStack public introuvable: {service_type}.")

    def _versioned_url(self, base_url: str, version: str) -> str:
        base_url = base_url.rstrip("/")
        if base_url.endswith(f"/{version}"):
            return base_url
        return f"{base_url}/{version}"

    async def _find_image_id(self, client: httpx.AsyncClient, token: str, image_url: str, image_name: str | None) -> str:
        if not image_name:
            raise ApiError(500, "openstack_image_missing", "TERRAFORM_IMAGE_NAME doit contenir le nom de l'image.")
        response = await client.get(
            f"{image_url}/images",
            params={"name": image_name, "status": "active"},
            headers={"X-Auth-Token": token},
        )
        if response.status_code != 200:
            raise ApiError(500, "openstack_image_lookup_failed", self._error_message(response))
        images = response.json().get("images", [])
        if not images:
            raise ApiError(404, "openstack_image_not_found", f"Image OpenStack introuvable: {image_name}.")
        return images[0]["id"]

    async def _find_flavor_id(self, client: httpx.AsyncClient, token: str, compute_url: str, flavor_name: str | None) -> str:
        if not flavor_name:
            raise ApiError(500, "openstack_flavor_missing", "TERRAFORM_DEFAULT_FLAVOR_NAME doit contenir le flavor.")
        response = await client.get(f"{compute_url}/flavors/detail", headers={"X-Auth-Token": token})
        if response.status_code != 200:
            raise ApiError(500, "openstack_flavor_lookup_failed", self._error_message(response))
        for flavor in response.json().get("flavors", []):
            if flavor.get("name") == flavor_name:
                return flavor["id"]
        raise ApiError(404, "openstack_flavor_not_found", f"Flavor OpenStack introuvable: {flavor_name}.")

    async def _resolve_network_id(self, client: httpx.AsyncClient, token: str, network_url: str) -> str:
        if self.settings.openstack_network_id:
            return self.settings.openstack_network_id
        response = await client.get(
            f"{network_url}/networks",
            params={"name": self.settings.openstack_network_name},
            headers={"X-Auth-Token": token},
        )
        if response.status_code != 200:
            raise ApiError(500, "openstack_network_lookup_failed", self._error_message(response))
        networks = response.json().get("networks", [])
        if not networks:
            raise ApiError(404, "openstack_network_not_found", f"Reseau OpenStack introuvable: {self.settings.openstack_network_name}.")
        return networks[0]["id"]

    async def _resolve_external_network_id(self, client: httpx.AsyncClient, token: str, network_url: str) -> str:
        response = await client.get(
            f"{network_url}/networks",
            params={"name": self.settings.terraform_external_network_name},
            headers={"X-Auth-Token": token},
        )
        if response.status_code != 200:
            raise ApiError(500, "openstack_external_network_lookup_failed", self._error_message(response))
        networks = response.json().get("networks", [])
        if not networks:
            raise ApiError(
                404,
                "openstack_external_network_not_found",
                f"Reseau externe OpenStack introuvable: {self.settings.terraform_external_network_name}.",
            )
        return networks[0]["id"]

    async def _find_server_port_id(self, client: httpx.AsyncClient, token: str, network_url: str, server_id: str) -> str:
        response = await client.get(
            f"{network_url}/ports",
            params={"device_id": server_id},
            headers={"X-Auth-Token": token},
        )
        if response.status_code != 200:
            raise ApiError(500, "openstack_port_lookup_failed", self._error_message(response))
        ports = response.json().get("ports", [])
        if not ports:
            raise ApiError(404, "openstack_port_not_found", f"Port reseau introuvable pour la VM {server_id}.")
        return ports[0]["id"]

    async def _assign_floating_ip(
        self,
        client: httpx.AsyncClient,
        token: str,
        network_url: str,
        server_id: str,
    ) -> str:
        external_network_id = await self._resolve_external_network_id(client, token, network_url)
        port_id = await self._find_server_port_id(client, token, network_url, server_id)
        response = await client.post(
            f"{network_url}/floatingips",
            headers={"X-Auth-Token": token},
            json={"floatingip": {"floating_network_id": external_network_id}},
        )
        if response.status_code not in {200, 201}:
            raise ApiError(500, "openstack_floating_ip_create_failed", self._error_message(response))
        floating_ip = response.json()["floatingip"]
        floating_ip_id = floating_ip["id"]
        try:
            associate = await client.put(
                f"{network_url}/floatingips/{floating_ip_id}",
                headers={"X-Auth-Token": token},
                json={"floatingip": {"port_id": port_id}},
            )
            if associate.status_code not in {200, 201}:
                raise ApiError(500, "openstack_floating_ip_attach_failed", self._error_message(associate))
            return associate.json()["floatingip"]["floating_ip_address"]
        except Exception:
            await client.delete(f"{network_url}/floatingips/{floating_ip_id}", headers={"X-Auth-Token": token})
            raise

    async def _create_server(
        self,
        client: httpx.AsyncClient,
        token: str,
        compute_url: str,
        *,
        name: str,
        image_id: str,
        flavor_id: str,
        network_id: str,
    ) -> dict[str, Any]:
        server: dict[str, Any] = {
            "name": name,
            "imageRef": image_id,
            "flavorRef": flavor_id,
            "networks": [{"uuid": network_id}],
            "key_name": self.settings.openstack_keypair_name,
        }
        if self.settings.openstack_availability_zone:
            server["availability_zone"] = self.settings.openstack_availability_zone
        if self.settings.openstack_security_group_name:
            server["security_groups"] = [{"name": self.settings.openstack_security_group_name}]
        response = await client.post(f"{compute_url}/servers", headers={"X-Auth-Token": token}, json={"server": server})
        if response.status_code != 202:
            raise ApiError(500, "openstack_server_create_failed", self._error_message(response))
        return response.json()["server"]

    async def _wait_for_server(self, client: httpx.AsyncClient, token: str, compute_url: str, server_id: str) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + self.settings.openstack_boot_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"{compute_url}/servers/{server_id}", headers={"X-Auth-Token": token})
            if response.status_code != 200:
                raise ApiError(500, "openstack_server_read_failed", self._error_message(response))
            server = response.json()["server"]
            status = server.get("status")
            if status == "ACTIVE":
                return server
            if status == "ERROR":
                raise ApiError(500, "openstack_server_error", f"OpenStack a retourne ERROR pour la VM {server_id}.")
            await asyncio.sleep(5)
        raise ApiError(504, "openstack_server_timeout", f"La VM {server_id} n'est pas ACTIVE apres le timeout.")

    def _first_private_ip(self, server: dict[str, Any]) -> str | None:
        for addresses in server.get("addresses", {}).values():
            for address in addresses:
                if address.get("OS-EXT-IPS:type") == "fixed" and address.get("addr"):
                    return address["addr"]
        return None

    def _network_segment(self, owner: User) -> str:
        return f"class-{(owner.class_name or 'staff').lower()}"

    def _vm_name(self, request: VmRequest, template: VmTemplate, index: int) -> str:
        slug = "".join(ch if ch.isalnum() else "-" for ch in template.name.lower()).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return f"cloud-lab-{slug}-{request.id:04d}-{index:02d}"

    def _error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text[-1200:]
        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, dict) and value.get("message"):
                    return str(value["message"])
            if data.get("error"):
                return str(data["error"])
        return response.text[-1200:]
