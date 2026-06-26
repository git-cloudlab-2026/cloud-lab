#!/usr/bin/env python3
import json
import os
import sys


def build_inventory() -> dict:
    vm_ip = os.environ.get("ANSIBLE_VM_IP", "").strip()
    ssh_user = os.environ.get("ANSIBLE_SSH_USER", "ubuntu").strip() or "ubuntu"
    private_key = os.environ.get("ANSIBLE_SSH_PRIVATE_KEY_PATH", "").strip()

    if not vm_ip:
        return {
            "all": {"children": ["cloud_lab_vms"]},
            "cloud_lab_vms": {"hosts": []},
            "_meta": {"hostvars": {}},
        }

    host_name = os.environ.get("ANSIBLE_VM_NAME", "cloud-lab-vm").strip() or "cloud-lab-vm"
    host_vars = {
        "ansible_host": vm_ip,
        "ansible_user": ssh_user,
        "ansible_python_interpreter": "/usr/bin/python3",
        "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
    }
    if private_key:
        host_vars["ansible_ssh_private_key_file"] = private_key

    return {
        "all": {"children": ["cloud_lab_vms"]},
        "cloud_lab_vms": {"hosts": [host_name]},
        "_meta": {"hostvars": {host_name: host_vars}},
    }


def main() -> None:
    inventory = build_inventory()
    if len(sys.argv) > 1 and sys.argv[1] == "--host":
        host = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(inventory.get("_meta", {}).get("hostvars", {}).get(host, {})))
        return
    print(json.dumps(inventory))


if __name__ == "__main__":
    main()
