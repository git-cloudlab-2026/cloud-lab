import { query, withTransaction } from "../db/pool.js";
import { ApiError } from "../middlewares/error-handler.js";

export async function listVirtualMachines(_req, res) {
  const { rows } = await query(`
    SELECT vm.*, u.full_name AS owner_name, r.course_id, c.name AS course_name
    FROM virtual_machines vm
    JOIN users u ON u.id = vm.owner_id
    JOIN vm_requests r ON r.id = vm.request_id
    JOIN courses c ON c.id = r.course_id
    ORDER BY vm.created_at DESC, vm.id DESC
  `);
  res.json({ data: rows });
}

export async function patchVirtualMachine(req, res) {
  const id = Number(req.params.id);
  const { status, actor_id = null } = req.body;

  const row = await withTransaction(async (client) => {
    const existing = await client.query("SELECT * FROM virtual_machines WHERE id = $1 FOR UPDATE", [id]);
    if (existing.rowCount === 0) throw new ApiError(404, "virtual_machine_not_found", "Machine virtuelle introuvable.");

    const destroyedAt = status === "destroyed" ? "now()" : "destroyed_at";
    const { rows } = await client.query(
      `UPDATE virtual_machines
       SET status = $1,
           destroyed_at = ${destroyedAt}
       WHERE id = $2
       RETURNING *`,
      [status, id]
    );

    await client.query(
      `INSERT INTO audit_events (actor_id, vm_id, request_id, event_type, severity, event_message)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        actor_id,
        id,
        existing.rows[0].request_id,
        `vm_${status}`,
        ["destroyed", "error"].includes(status) ? "warning" : "info",
        `VM #${id} mise a jour vers ${status}.`
      ]
    );

    return rows[0];
  });

  res.json({ data: row });
}
