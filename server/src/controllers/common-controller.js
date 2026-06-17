import { query } from "../db/pool.js";

export async function listCourses(_req, res) {
  const { rows } = await query("SELECT * FROM courses ORDER BY id");
  res.json({ data: rows });
}

export async function listVmTemplates(_req, res) {
  const { rows } = await query("SELECT * FROM vm_templates ORDER BY id");
  res.json({ data: rows });
}

export async function listVmMetrics(_req, res) {
  const { rows } = await query("SELECT * FROM vm_metrics ORDER BY collected_at DESC, id DESC");
  res.json({ data: rows });
}

export async function listCostRecords(_req, res) {
  const { rows } = await query("SELECT * FROM cost_records ORDER BY cost_date DESC, id DESC");
  res.json({ data: rows });
}
