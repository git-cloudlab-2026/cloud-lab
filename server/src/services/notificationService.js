import { query } from "../db/pool.js";
import { sendEmail } from "./emailAdapter.js";

function getRunner(client) {
  return client || { query };
}

export async function createNotification(userId, type, title, message, options = {}) {
  const runner = getRunner(options.client);
  const metadata = options.metadata || {};

  const { rows } = await runner.query(
    `INSERT INTO notifications (user_id, type, title, message, metadata)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING *`,
    [userId, type, title, message, metadata]
  );

  if (options.email) {
    await sendEmail({
      to: options.email,
      subject: title,
      text: message
    });
  }

  return rows[0];
}

export async function listNotifications(userId, { unreadOnly = false } = {}) {
  const filters = ["user_id = $1"];
  const values = [userId];

  if (unreadOnly) {
    filters.push("is_read = false");
  }

  const { rows } = await query(
    `SELECT *
     FROM notifications
     WHERE ${filters.join(" AND ")}
     ORDER BY created_at DESC, id DESC`,
    values
  );

  return rows;
}

export async function markNotificationAsRead(userId, notificationId) {
  const { rows } = await query(
    `UPDATE notifications
     SET is_read = true
     WHERE id = $1 AND user_id = $2
     RETURNING *`,
    [notificationId, userId]
  );

  return rows[0] || null;
}

