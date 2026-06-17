import { query } from "../db/pool.js";

export async function listAuditEvents(req, res) {
  const { type, severity, actor } = req.query;
  const conditions = [];
  const params = [];

  if (type) {
    params.push(type);
    conditions.push(`e.event_type = $${params.length}`);
  }
  if (severity) {
    params.push(severity);
    conditions.push(`e.severity = $${params.length}`);
  }
  if (actor) {
    params.push(`%${actor}%`);
    conditions.push(`u.full_name ILIKE $${params.length}`);
  }

  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  const { rows } = await query(
    `SELECT e.*, u.full_name AS actor_name, u.role AS actor_role
     FROM audit_events e
     LEFT JOIN users u ON u.id = e.actor_id
     ${where}
     ORDER BY e.created_at DESC, e.id DESC`,
    params
  );
  res.json({ data: rows });
}
