from sqlalchemy import select

from app.domain.models import Course, VmTemplate
from app.repositories.base import Repository


class CourseRepository(Repository[Course]):
    model = Course


class VmTemplateRepository(Repository[VmTemplate]):
    model = VmTemplate

    async def list_active(self) -> list[VmTemplate]:
        result = await self.session.execute(select(VmTemplate).where(VmTemplate.is_active.is_(True)).order_by(VmTemplate.id))
        return list(result.scalars())
