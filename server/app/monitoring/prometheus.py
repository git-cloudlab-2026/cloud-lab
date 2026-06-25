from decimal import Decimal
from typing import Any

from fastapi import Response
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.domain.models import CostRecord, VirtualMachine, VmMetric, VmRequest


CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


def _label(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value: Any) -> str:
    if value is None:
        return "0"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _sample(name: str, labels: dict[str, Any], value: Any) -> str:
    rendered_labels = ",".join(f'{key}="{_label(label_value)}"' for key, label_value in labels.items())
    return f"{name}{{{rendered_labels}}} {_number(value)}"


async def render_prometheus_metrics() -> Response:
    async with SessionLocal() as session:
        vm_counts = await session.execute(
            select(VirtualMachine.status, func.count(VirtualMachine.id)).group_by(VirtualMachine.status)
        )
        request_counts = await session.execute(select(VmRequest.status, func.count(VmRequest.id)).group_by(VmRequest.status))
        cost_total = await session.scalar(select(func.coalesce(func.sum(CostRecord.cost_estimate_chf), 0)))

        latest_metric_at = (
            select(VmMetric.vm_id, func.max(VmMetric.collected_at).label("collected_at"))
            .group_by(VmMetric.vm_id)
            .subquery()
        )
        latest_metrics = await session.execute(
            select(VirtualMachine, VmMetric)
            .join(latest_metric_at, latest_metric_at.c.vm_id == VirtualMachine.id, isouter=True)
            .join(
                VmMetric,
                (VmMetric.vm_id == VirtualMachine.id) & (VmMetric.collected_at == latest_metric_at.c.collected_at),
                isouter=True,
            )
            .order_by(VirtualMachine.id)
        )

    lines = [
        "# HELP cloud_lab_vms_total Number of virtual machines by lifecycle status.",
        "# TYPE cloud_lab_vms_total gauge",
    ]
    for status, count in vm_counts:
        lines.append(_sample("cloud_lab_vms_total", {"status": status.value}, count))

    lines.extend(
        [
            "# HELP cloud_lab_requests_total Number of VM requests by workflow status.",
            "# TYPE cloud_lab_requests_total gauge",
        ]
    )
    for status, count in request_counts:
        lines.append(_sample("cloud_lab_requests_total", {"status": status.value}, count))

    lines.extend(
        [
            "# HELP cloud_lab_cost_estimate_chf_total Estimated Cloud Lab cost in CHF.",
            "# TYPE cloud_lab_cost_estimate_chf_total gauge",
            f"cloud_lab_cost_estimate_chf_total {_number(cost_total)}",
            "# HELP cloud_lab_vm_up Virtual machine availability from Cloud Lab state.",
            "# TYPE cloud_lab_vm_up gauge",
            "# HELP cloud_lab_vm_cpu_usage_percent Latest VM CPU usage percent.",
            "# TYPE cloud_lab_vm_cpu_usage_percent gauge",
            "# HELP cloud_lab_vm_ram_usage_percent Latest VM RAM usage percent.",
            "# TYPE cloud_lab_vm_ram_usage_percent gauge",
            "# HELP cloud_lab_vm_disk_usage_percent Latest VM disk usage percent.",
            "# TYPE cloud_lab_vm_disk_usage_percent gauge",
            "# HELP cloud_lab_vm_info Static VM information.",
            "# TYPE cloud_lab_vm_info gauge",
        ]
    )

    for vm, metric in latest_metrics:
        labels = {
            "vm": vm.name,
            "status": vm.status.value,
            "owner_id": vm.owner_id,
            "provider_vm_id": vm.provider_vm_id or "",
            "ip_address": vm.ip_address or "",
            "network_segment": vm.network_segment or "",
        }
        lines.append(_sample("cloud_lab_vm_up", labels, 1 if vm.status.value == "running" else 0))
        lines.append(_sample("cloud_lab_vm_info", labels, 1))
        if metric:
            lines.append(_sample("cloud_lab_vm_cpu_usage_percent", labels, metric.cpu_usage_percent))
            lines.append(_sample("cloud_lab_vm_ram_usage_percent", labels, metric.ram_usage_percent))
            lines.append(_sample("cloud_lab_vm_disk_usage_percent", labels, metric.disk_usage_percent))

    return Response("\n".join(lines) + "\n", media_type=CONTENT_TYPE_LATEST)
