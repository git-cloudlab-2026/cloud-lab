import asyncio

from app.db.session import AsyncSessionLocal
from app.jobs.lifecycle import VmLifecycleJob


async def main() -> None:
    async with AsyncSessionLocal() as session:
        expired_vms = await VmLifecycleJob(session).mark_expired_vms()
        await session.commit()
        print(f"{len(expired_vms)} VM(s) marquees comme expired.")


if __name__ == "__main__":
    asyncio.run(main())
