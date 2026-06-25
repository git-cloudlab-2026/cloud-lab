import asyncio

from sqlalchemy import select

from app.db.session import SessionLocal
from app.domain.models import VirtualMachine


async def main() -> None:
    async with SessionLocal() as session:
        demo_vms = (
            await session.execute(
                select(VirtualMachine).where(VirtualMachine.name.like("git-%"))
            )
        ).scalars().all()

        for vm in demo_vms:
            await session.delete(vm)

        await session.commit()

        remaining = (
            await session.execute(select(VirtualMachine.name, VirtualMachine.ip_address))
        ).all()

    print(f"VM demo supprimees: {len(demo_vms)}")
    for name, ip_address in remaining:
        print(f"- {name} {ip_address or ''}")


if __name__ == "__main__":
    asyncio.run(main())
