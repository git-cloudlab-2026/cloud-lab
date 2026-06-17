-- Requetes utiles pour le dashboard data / monitoring / couts

-- 1. Nombre de VM actives
SELECT COUNT(*) AS active_vms
FROM virtual_machines
WHERE status = 'running';

-- 2. Nombre de demandes en attente
SELECT COUNT(*) AS pending_requests
FROM vm_requests
WHERE status = 'pending';

-- 3. Nombre de VM expirees non detruites
SELECT COUNT(*) AS expired_vms
FROM virtual_machines
WHERE status = 'expired';

-- 4. Cout total du jour
SELECT COALESCE(SUM(cost_estimate_chf), 0) AS today_cost_chf
FROM cost_records
WHERE cost_date = DATE('now');

-- 5. Cout total par cours
SELECT
    c.name AS course_name,
    COUNT(vm.id) AS vm_count,
    COALESCE(SUM(cr.cost_estimate_chf), 0) AS total_cost_chf
FROM courses c
JOIN vm_requests r ON r.course_id = c.id
JOIN virtual_machines vm ON vm.request_id = r.id
LEFT JOIN cost_records cr ON cr.vm_id = vm.id
GROUP BY c.id, c.name
ORDER BY total_cost_chf DESC;

-- 6. Demandes en attente avec cout estime
SELECT
    r.id AS request_id,
    u.full_name AS requester,
    u.role AS requester_role,
    c.name AS course_name,
    t.name AS template_name,
    r.quantity,
    r.start_date,
    r.end_date,
    ROUND(
        r.quantity *
        (JULIANDAY(r.end_date) - JULIANDAY(r.start_date)) *
        24 *
        t.estimated_cost_per_hour_chf,
        2
    ) AS estimated_total_cost_chf
FROM vm_requests r
JOIN users u ON u.id = r.requester_id
JOIN courses c ON c.id = r.course_id
JOIN vm_templates t ON t.id = r.template_id
WHERE r.status = 'pending'
ORDER BY r.created_at ASC;

-- 7. Machines qui expirent bientot
SELECT
    vm.name AS vm_name,
    u.full_name AS owner_name,
    vm.ip_address,
    vm.status,
    vm.end_date
FROM virtual_machines vm
JOIN users u ON u.id = vm.owner_id
WHERE vm.status IN ('running', 'stopped', 'down')
  AND vm.end_date <= DATE('now', '+2 day')
ORDER BY vm.end_date ASC;

-- 8. Dernieres metriques par VM
SELECT
    vm.name AS vm_name,
    m.cpu_usage_percent,
    m.ram_usage_percent,
    m.disk_usage_percent,
    m.state,
    m.collected_at
FROM vm_metrics m
JOIN virtual_machines vm ON vm.id = m.vm_id
WHERE m.collected_at = (
    SELECT MAX(m2.collected_at)
    FROM vm_metrics m2
    WHERE m2.vm_id = m.vm_id
)
ORDER BY m.collected_at DESC;

-- 9. VM potentiellement inactives
SELECT
    vm.name AS vm_name,
    u.full_name AS owner_name,
    AVG(m.cpu_usage_percent) AS avg_cpu,
    AVG(m.ram_usage_percent) AS avg_ram,
    MAX(m.collected_at) AS last_metric_at
FROM virtual_machines vm
JOIN users u ON u.id = vm.owner_id
JOIN vm_metrics m ON m.vm_id = vm.id
WHERE vm.status = 'running'
GROUP BY vm.id, vm.name, u.full_name
HAVING AVG(m.cpu_usage_percent) < 5
ORDER BY avg_cpu ASC;

-- 10. Historique des evenements
SELECT
    e.created_at,
    e.event_type,
    e.event_message,
    u.full_name AS actor_name,
    e.request_id,
    e.vm_id
FROM audit_events e
LEFT JOIN users u ON u.id = e.actor_id
ORDER BY e.created_at DESC;

