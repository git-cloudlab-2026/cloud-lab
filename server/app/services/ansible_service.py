import asyncio
import ipaddress
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class AnsibleResult:
    skipped: bool
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class AnsibleService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.project_root = Path(__file__).resolve().parents[3]

    async def run_playbook(
        self,
        vm_ip: str | None,
        template_type: str,
        vm_name: str,
        end_date: str,
        course_name: str | None = None,
        request_id: int | None = None,
        ssh_user: str | None = None,
    ) -> AnsibleResult:
        if not self.settings.ansible_enabled:
            return AnsibleResult(skipped=True, stdout="Ansible disabled by ANSIBLE_ENABLED=false.")

        if not vm_ip:
            raise ApiError(500, "ansible_missing_vm_ip", "Configuration Ansible impossible: IP VM absente.")

        target_ip = self.select_target_ip(vm_ip)
        source_private_key = self._find_private_key(request_id)
        if not source_private_key or not source_private_key.exists():
            raise ApiError(
                500,
                "ansible_missing_private_key",
                "Configuration Ansible impossible: cle privee SSH introuvable.",
            )

        playbook = self._resolve_path(self.settings.ansible_playbook_path)
        ansible_config = self._resolve_path(f"{self.settings.ansible_project_dir}/ansible.cfg")
        for path, code in {
            playbook: "ansible_missing_playbook",
            ansible_config: "ansible_missing_config",
        }.items():
            if not path.exists():
                raise ApiError(500, code, f"Configuration Ansible impossible: fichier absent {path}.")

        normalized_template_type = self.normalize_template_type(template_type)
        extra_vars = {
            "template_type": normalized_template_type,
            "vm_name": vm_name,
            "course_name": course_name or "Cloud Lab",
            "end_date": end_date,
            "student_user": self.settings.ansible_student_user,
        }
        env = os.environ.copy()
        temp_private_key = self._prepare_private_key(source_private_key)
        resolved_ssh_user = ssh_user or self.settings.ansible_ssh_user
        env.update(
            {
                "ANSIBLE_CONFIG": str(ansible_config),
                "ANSIBLE_VM_IP": target_ip,
                "ANSIBLE_VM_NAME": vm_name,
                "ANSIBLE_SSH_USER": resolved_ssh_user,
                "ANSIBLE_SSH_PRIVATE_KEY_PATH": str(temp_private_key),
            }
        )

        try:
            process = await asyncio.create_subprocess_exec(
                self.settings.ansible_binary,
                "-i",
                f"{target_ip},",
                "--user",
                resolved_ssh_user,
                "--private-key",
                str(temp_private_key),
                str(playbook),
                "--extra-vars",
                json.dumps(extra_vars),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.settings.ansible_timeout_seconds,
                )
            except TimeoutError as exc:
                process.kill()
                await process.communicate()
                raise ApiError(
                    500,
                    "ansible_timeout",
                    f"Configuration Ansible trop longue apres {self.settings.ansible_timeout_seconds}s.",
                ) from exc
        finally:
            temp_private_key.unlink(missing_ok=True)

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        if "skipping: no hosts matched" in stdout.lower():
            raise ApiError(
                500,
                "ansible_no_hosts_matched",
                "Configuration Ansible echouee: aucun host cible. Verification de l'inventaire inline requise.",
            )
        if process.returncode != 0:
            details = self._tail(stderr or stdout)
            raise ApiError(500, "ansible_playbook_failed", f"Configuration Ansible echouee: {details}")

        return AnsibleResult(skipped=False, returncode=process.returncode, stdout=stdout, stderr=stderr)

    @staticmethod
    def select_target_ip(value: str) -> str:
        candidates = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", value or "")
        parsed: list[tuple[str, ipaddress.IPv4Address | ipaddress.IPv6Address]] = []
        for candidate in candidates:
            try:
                parsed.append((candidate, ipaddress.ip_address(candidate)))
            except ValueError:
                continue

        public_candidates = [
            candidate
            for candidate, address in parsed
            if not address.is_private and not address.is_loopback and not address.is_link_local
        ]
        if public_candidates:
            return public_candidates[0]
        if parsed:
            return parsed[0][0]
        return value.strip()

    def _resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    def _resolve_optional_path(self, value: str | None) -> Path | None:
        if not value:
            return None
        return self._resolve_path(value)

    def _find_private_key(self, request_id: int | None) -> Path | None:
        configured_key = self._resolve_optional_path(self.settings.ansible_ssh_private_key_path)
        if configured_key and configured_key.exists():
            return configured_key

        work_dir = self._resolve_optional_path(self.settings.terraform_work_dir)
        if not work_dir or not work_dir.exists():
            return None

        candidates: list[Path] = []
        if request_id is not None:
            candidates.extend(
                [
                    work_dir / f"request-{request_id:04d}" / "cloud-lab-key",
                    work_dir / f"request-{request_id}" / "cloud-lab-key",
                ]
            )
        candidates.extend(sorted(work_dir.glob("request-*/cloud-lab-key"), key=lambda path: path.stat().st_mtime, reverse=True))
        return next((path for path in candidates if path.exists()), None)

    @staticmethod
    def _prepare_private_key(source_private_key: Path) -> Path:
        with tempfile.NamedTemporaryFile("wb", suffix=".key", delete=False) as key_file:
            key_file.write(source_private_key.read_bytes())
            key_path = Path(key_file.name)
        key_path.chmod(0o600)
        return key_path

    @staticmethod
    def normalize_template_type(template_type: str | None) -> str:
        value = (template_type or "").lower()
        replacements = {
            "é": "e",
            "è": "e",
            "ê": "e",
            "à": "a",
            "ç": "c",
            "û": "u",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
        if "admin" in value or "linux" in value:
            return "admin_linux"
        if "dev" in value or "web" in value:
            return "dev_web"
        if "data" in value or "science" in value or "donnee" in value:
            return "data_science"
        if "cyber" in value or "secur" in value:
            return "cybersecurity"
        return "base"

    @staticmethod
    def _tail(value: str, limit: int = 1200) -> str:
        clean = (value or "").replace("\x00", "").strip()
        return clean[-limit:] if len(clean) > limit else clean
