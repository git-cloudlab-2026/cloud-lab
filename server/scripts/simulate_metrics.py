import asyncio
import random

from sqlalchemy import select

from app.db.session import SessionLocal
from app.domain.enums import MetricState, VmStatus
from app.domain.models import VirtualMachine, VmMetric


async def main() -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(VirtualMachine).where(VirtualMachine.status == VmStatus.running))
        for vm in result.scalars():
            session.add(
                VmMetric(
                    vm_id=vm.id,
                    cpu_usage_percent=random.randint(3, 80),
                    ram_usage_percent=random.randint(20, 85),
                    disk_usage_percent=random.randint(15, 70),
                    state=MetricState.up,
                )
            )
        await session.commit()
    print("Métriques de démonstration insérées.")


if __name__ == "__main__":
    asyncio.run(main())
