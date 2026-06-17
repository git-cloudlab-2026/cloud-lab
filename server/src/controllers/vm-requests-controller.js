import { query, withTransaction } from "../db/pool.js";
import { ApiError } from "../middlewares/error-handler.js";

export async function listVmRequests(_req, res) {
  const { rows } = await query(`
    SELECT r.*, u.full_name AS requester_name, c.name AS course_name, t.name AS template_name
    FROM vm_requests r
    JOIN users u ON u.id = r.requester_id
    JOIN courses c ON c.id = r.course_id
    JOIN vm_templates t ON t.id = r.template_id
    ORDER BY r.created_at DESC, r.id DESC
  `);
  res.json({ data: rows });
}

export async function createVmRequest(req, res) {
  const payload = req.body;
  const row = await withTransaction(async (client) => {
    const { rows } = await client.query(
      `INSERT INTO vm_requests (requester_id, course_id, template_id, quantity, start_date, end_date, status, request_reason)
       VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
       RETURNING *`,
      [
        payload.requester_id,
        payload.course_id,
        payload.template_id,
        payload.quantity,
        payload.start_date,
        payload.end_date,
        payload.request_reason || null
      ]
    );
    const request = rows[0];
    await client.query(
      `INSERT INTO audit_events (actor_id, request_id, event_type, severity, event_message)
       VALUES ($1, $2, 'request_created', 'success', $3)`,
      [request.requester_id, request.id, `Demande #${request.id} creee.`]
    );
    return request;
  });
  res.status(201).json({ data: row });
}

export async function patchVmRequest(req, res) {
  const id = Number(req.params.id);
  const { status, validator_id = null, decision_comment = null } = req.body;

  const row = await withTransaction(async (client) => {
    const existing = await client.query("SELECT * FROM vm_requests WHERE id = $1 FOR UPDATE", [id]);
    if (existing.rowCount === 0) throw new ApiError(404, "vm_request_not_found", "Demande VM introuvable.");

    const { rows } = await client.query(
      `UPDATE vm_requests
       SET status = $1,
           validator_id = COALESCE($2, validator_id),
           decision_comment = COALESCE($3, decision_comment),
           updated_at = now()
       WHERE id = $4
       RETURNING *`,
      [status, validator_id, decision_comment, id]
    );

    await client.query(
      `INSERT INTO audit_events (actor_id, request_id, event_type, severity, event_message)
       VALUES ($1, $2, $3, $4, $5)`,
      [
        validator_id,
        id,
        `request_${status}`,
        ["approved", "provisioned"].includes(status) ? "success" : status === "refused" ? "warning" : "info",
        `Demande #${id} mise a jour vers ${status}.`
      ]
    );

    return rows[0];
  });

  res.json({ data: row });
}
