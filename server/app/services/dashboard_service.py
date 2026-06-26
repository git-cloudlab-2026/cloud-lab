from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cost_service import CostService


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def summary(self) -> dict:
        await CostService(self.session).refresh_all()
        await self.session.commit()

        queries = {
            "active_vms": "SELECT COUNT(*)::int AS value FROM virtual_machines WHERE status = 'running'",
            "pending_requests": "SELECT COUNT(*)::int AS value FROM vm_requests WHERE status = 'pending'",
            "expired_vms": "SELECT COUNT(*)::int AS value FROM virtual_machines WHERE status = 'expired'",
            "today_cost_chf": "SELECT COALESCE(SUM(cost_estimate_chf), 0)::numeric(10,2) AS value FROM cost_records WHERE cost_date = CURRENT_DATE",
        }
        scalar_results = {}
        for key, sql in queries.items():
            result = await self.session.execute(text(sql))
            scalar_results[key] = result.mappings().one()["value"]

        async def rows(sql: str) -> list[dict]:
            result = await self.session.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]

        return {
            **scalar_results,
            "cost_by_course": await rows(
                """
                SELECT c.id AS course_id, c.name AS course_name, COUNT(vm.id)::int AS vm_count,
                       COALESCE(SUM(cr.cost_estimate_chf), 0)::numeric(10,2) AS total_cost_chf
                FROM courses c
                LEFT JOIN vm_requests r ON r.course_id = c.id
                LEFT JOIN virtual_machines vm ON vm.request_id = r.id
                LEFT JOIN cost_records cr ON cr.vm_id = vm.id
                GROUP BY c.id, c.name
                ORDER BY total_cost_chf DESC
                """
            ),
            "pending_requests_with_cost": await rows(
                """
                SELECT r.id AS request_id, u.full_name AS requester, c.name AS course_name, t.name AS template_name,
                       r.quantity, r.start_date, r.end_date,
                       ROUND((r.quantity * (r.end_date - r.start_date) * 24 * t.estimated_cost_per_hour_chf)::numeric, 2) AS estimated_total_cost_chf
                FROM vm_requests r
                JOIN users u ON u.id = r.requester_id
                JOIN courses c ON c.id = r.course_id
                JOIN vm_templates t ON t.id = r.template_id
                WHERE r.status = 'pending'
                ORDER BY r.created_at ASC
                """
            ),
            "expiring_soon": await rows("SELECT * FROM expiring_vms ORDER BY end_date ASC"),
            "audit_events": await rows("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT 50"),
        }
