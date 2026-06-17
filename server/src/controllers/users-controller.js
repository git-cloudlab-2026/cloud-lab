import { query } from "../db/pool.js";

export async function listUsers(_req, res) {
  const { rows } = await query("SELECT * FROM users ORDER BY id");
  res.json({ data: rows });
}

export async function createUser(req, res) {
  const { full_name, email, role, class_name = null, is_active = true } = req.body;
  const { rows } = await query(
    `INSERT INTO users (full_name, email, role, class_name, is_active)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING *`,
    [full_name, email, role, class_name, is_active]
  );
  res.status(201).json({ data: rows[0] });
}
