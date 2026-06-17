import { query } from "../db/pool.js";

export async function getDashboardSummary(_req, res) {
  const [
    activeVms,
    pendingRequests,
    expiredVms,
    todayCost,
    costByCourse,
    pendingRequestsWithCost,
    expiringSoon,
    latestMetrics,
    inactiveVms,
    events
  ] = await Promise.all([
    query("SELECT COUNT(*)::int AS active_vms FROM virtual_machines WHERE status = 'running'"),
    query("SELECT COUNT(*)::int AS pending_requests FROM vm_requests WHERE status = 'pending'"),
    query("SELECT COUNT(*)::int AS expired_vms FROM virtual_machines WHERE status = 'expired'"),
    query("SELECT COALESCE(SUM(cost_estimate_chf), 0)::numeric(10,2) AS today_cost_chf FROM cost_records WHERE cost_date = CURRENT_DATE"),
    query(`
      SELECT
        c.id AS course_id,
        c.name AS course_name,
        COUNT(vm.id)::int AS vm_count,
        COALESCE(SUM(cr.cost_estimate_chf), 0)::numeric(10,2) AS total_cost_chf
      FROM courses c
      JOIN vm_requests r ON r.course_id = c.id
      JOIN virtual_machines vm ON vm.request_id = r.id
      LEFT JOIN cost_records cr ON cr.vm_id = vm.id
      GROUP BY c.id, c.name
      ORDER BY total_cost_chf DESC
    `),
    query(`
      SELECT
        r.id AS request_id,
        u.full_name AS requester,
        u.role AS requester_role,
        c.name AS course_name,
        t.name AS template_name,
        r.quantity,
        r.start_date,
        r.end_date,
        ROUND((r.quantity * (r.end_date - r.start_date) * 24 * t.estimated_cost_per_hour_chf)::numeric, 2) AS estimated_total_cost_chf
      FROM vm_requests r
      JOIN users u ON u.id = r.requester_id
      JOIN courses c ON c.id = r.course_id
      JOIN vm_templates t ON t.id = r.template_id
      WHERE r.status = 'pending'
      ORDER BY r.created_at ASC
    `),
    query(`
      SELECT
        vm.name AS vm_name,
        u.full_name AS owner_name,
        vm.ip_address,
        vm.status,
        vm.end_date
      FROM virtual_machines vm
      JOIN users u ON u.id = vm.owner_id
      WHERE vm.status IN ('running', 'stopped', 'down')
        AND vm.end_date <= (CURRENT_DATE + INTERVAL '2 days')
      ORDER BY vm.end_date ASC
    `),
    query(`
      SELECT DISTINCT ON (vm.id)
        vm.id AS vm_id,
        vm.name AS vm_name,
        m.cpu_usage_percent,
        m.ram_usage_percent,
        m.disk_usage_percent,
        m.state,
        m.collected_at
      FROM virtual_machines vm
      JOIN vm_metrics m ON m.vm_id = vm.id
      ORDER BY vm.id, m.collected_at DESC
    `),
    query(`
      SELECT
        vm.id AS vm_id,
        vm.name AS vm_name,
        u.full_name AS owner_name,
        AVG(m.cpu_usage_percent)::numeric(5,2) AS avg_cpu,
        AVG(m.ram_usage_percent)::numeric(5,2) AS avg_ram,
        MAX(m.collected_at) AS last_metric_at
      FROM virtual_machines vm
      JOIN users u ON u.id = vm.owner_id
      JOIN vm_metrics m ON m.vm_id = vm.id
      WHERE vm.status = 'running'
      GROUP BY vm.id, vm.name, u.full_name
      HAVING AVG(m.cpu_usage_percent) < 5
      ORDER BY avg_cpu ASC
    `),
    query(`
      SELECT
        e.created_at,
        e.event_type,
        e.severity,
        e.event_message,
        u.full_name AS actor_name,
        e.request_id,
        e.vm_id
      FROM audit_events e
      LEFT JOIN users u ON u.id = e.actor_id
      ORDER BY e.created_at DESC
      LIMIT 50
    `)
  ]);

  res.json({
    data: {
      active_vms: activeVms.rows[0].active_vms,
      pending_requests: pendingRequests.rows[0].pending_requests,
      expired_vms: expiredVms.rows[0].expired_vms,
      today_cost_chf: todayCost.rows[0].today_cost_chf,
      cost_by_course: costByCourse.rows,
      pending_requests_with_cost: pendingRequestsWithCost.rows,
      expiring_soon: expiringSoon.rows,
      latest_metrics: latestMetrics.rows,
      potentially_inactive_vms: inactiveVms.rows,
      audit_events: events.rows
    }
  });
}
