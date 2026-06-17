import { query, withTransaction } from "../db/pool.js";
import { ApiError } from "../middlewares/error-handler.js";
import { createNotification } from "../services/notificationService.js";

const vmStatuses = ["creating", "running", "stopped", "down", "expired", "destroyed", "error"];

export async function listVirtualMachines(req, res) {
  const values = [];
  const filters = [];

  if (req.query.status) {
    if (!vmStatuses.includes(req.query.status)) {
      throw new ApiError(400, "invalid_vm_status", `Statut VM invalide: ${req.query.status}.`);
    }
    values.push(req.query.status);
    filters.push(`vm.status = $${values.length}`);
  }

  const whereClause = filters.length > 0 ? `WHERE ${filters.join(" AND ")}` : "";

  const { rows } = await query(`
    SELECT vm.*, u.full_name AS owner_name, r.course_id, c.name AS course_name
    FROM virtual_machines vm
    JOIN users u ON u.id = vm.owner_id
    JOIN vm_requests r ON r.id = vm.request_id
    JOIN courses c ON c.id = r.course_id
    ${whereClause}
    ORDER BY vm.created_at DESC, vm.id DESC
  `, values);
  res.json({ data: rows });
}

export async function patchVirtualMachine(req, res) {
  const id = Number(req.params.id);
  const { status, actor_id = null } = req.body;
  const actorId = req.user.id;

  if (actor_id && actor_id !== actorId) {
    throw new ApiError(403, "actor_mismatch", "Le actor_id doit correspondre a l'utilisateur connecte.");
  }

  const row = await withTransaction(async (client) => {
    const existing = await client.query(
      `SELECT vm.*, u.email AS owner_email
       FROM virtual_machines vm
       JOIN users u ON u.id = vm.owner_id
       WHERE vm.id = $1
       FOR UPDATE OF vm`,
      [id]
    );
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
        actorId,
        id,
        existing.rows[0].request_id,
        `vm_${status}`,
        ["destroyed", "error"].includes(status) ? "warning" : "info",
        `VM #${id} mise a jour vers ${status}.`
      ]
    );

    if (status === "destroyed") {
      const vm = existing.rows[0];
      await createNotification(
        vm.owner_id,
        "vm_destroyed",
        "Votre VM a ete detruite",
        `La machine ${vm.name} a ete detruite et les ressources cloud ont ete liberees.`,
        {
          client,
          email: vm.owner_email,
          metadata: {
            vm_id: id,
            request_id: vm.request_id
          }
        }
      );
    }

    return rows[0];
  });

  res.json({ data: row });
}

export async function patchProvisioningResult(req, res) {
  const id = Number(req.params.id);
  const actorId = req.user.id;
  const { provider_vm_id, ip_address = null, status, network_segment = null } = req.body;

  const row = await withTransaction(async (client) => {
    const existing = await client.query(
      `SELECT vm.*, u.email AS owner_email
       FROM virtual_machines vm
       JOIN users u ON u.id = vm.owner_id
       WHERE vm.id = $1
       FOR UPDATE OF vm`,
      [id]
    );
    if (existing.rowCount === 0) throw new ApiError(404, "virtual_machine_not_found", "Machine virtuelle introuvable.");

    const { rows } = await client.query(
      `UPDATE virtual_machines
       SET provider_vm_id = $1,
           ip_address = $2,
           status = $3,
           network_segment = $4
       WHERE id = $5
       RETURNING *`,
      [provider_vm_id, ip_address, status, network_segment, id]
    );

    const isSuccess = status !== "error";
    await client.query(
      `INSERT INTO audit_events (actor_id, vm_id, request_id, event_type, severity, event_message)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        actorId,
        id,
        existing.rows[0].request_id,
        isSuccess ? "vm_provisioned" : "vm_provisioning_failed",
        isSuccess ? "success" : "danger",
        isSuccess
          ? `VM #${id} provisionnee par le service externe.`
          : `Provisioning echoue pour la VM #${id}.`
      ]
    );

    return rows[0];
  });

  res.json({ data: row });
}

export async function patchDestructionResult(req, res) {
  const id = Number(req.params.id);
  const actorId = req.user.id;
  const { destroyed_at = null } = req.body;

  const row = await withTransaction(async (client) => {
    const existing = await client.query(
      `SELECT vm.*, u.email AS owner_email
       FROM virtual_machines vm
       JOIN users u ON u.id = vm.owner_id
       WHERE vm.id = $1
       FOR UPDATE OF vm`,
      [id]
    );
    if (existing.rowCount === 0) throw new ApiError(404, "virtual_machine_not_found", "Machine virtuelle introuvable.");

    const { rows } = await client.query(
      `UPDATE virtual_machines
       SET status = 'destroyed',
           destroyed_at = COALESCE($1::timestamptz, now())
       WHERE id = $2
       RETURNING *`,
      [destroyed_at, id]
    );

    const vm = existing.rows[0];
    await client.query(
      `INSERT INTO audit_events (actor_id, vm_id, request_id, event_type, severity, event_message)
       VALUES ($1, $2, $3, 'vm_destroyed', 'warning', $4)`,
      [actorId, id, vm.request_id, `Destruction confirmee pour la VM #${id} par le service externe.`]
    );

    await createNotification(
      vm.owner_id,
      "vm_destroyed",
      "Votre VM a ete detruite",
      `La machine ${vm.name} a ete detruite et les ressources cloud ont ete liberees.`,
      {
        client,
        email: vm.owner_email,
        metadata: {
          vm_id: id,
          request_id: vm.request_id
        }
      }
    );

    return rows[0];
  });

  res.json({ data: row });
}

export async function createVirtualMachineMetric(req, res) {
  const id = Number(req.params.id);
  const { cpu_usage_percent = null, ram_usage_percent = null, disk_usage_percent = null, state = "unknown" } = req.body;

  const row = await withTransaction(async (client) => {
    const existing = await client.query("SELECT id FROM virtual_machines WHERE id = $1", [id]);
    if (existing.rowCount === 0) throw new ApiError(404, "virtual_machine_not_found", "Machine virtuelle introuvable.");

    const { rows } = await client.query(
      `INSERT INTO vm_metrics (vm_id, cpu_usage_percent, ram_usage_percent, disk_usage_percent, state)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING *`,
      [id, cpu_usage_percent, ram_usage_percent, disk_usage_percent, state]
    );

    await client.query(
      `INSERT INTO audit_events (actor_id, vm_id, event_type, severity, event_message)
       VALUES ($1, $2, 'vm_metric_received', 'info', $3)`,
      [req.user.id, id, `Metrie recue pour la VM #${id}.`]
    );

    return rows[0];
  });

  res.status(201).json({ data: row });
}

export async function listVirtualMachineMetricHistory(req, res) {
  const id = Number(req.params.id);
  const limit = Math.min(Math.max(Number(req.query.limit || 50), 1), 500);

  const existing = await query("SELECT id FROM virtual_machines WHERE id = $1", [id]);
  if (existing.rowCount === 0) throw new ApiError(404, "virtual_machine_not_found", "Machine virtuelle introuvable.");

  const { rows } = await query(
    `SELECT *
     FROM vm_metrics
     WHERE vm_id = $1
     ORDER BY collected_at DESC, id DESC
     LIMIT $2`,
    [id, limit]
  );

  res.json({ data: rows });
}
