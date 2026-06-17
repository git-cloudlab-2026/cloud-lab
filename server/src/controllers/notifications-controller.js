import { ApiError } from "../middlewares/error-handler.js";
import { listNotifications, markNotificationAsRead } from "../services/notificationService.js";

export async function getNotifications(req, res) {
  const unreadOnly = ["true", "1", "yes"].includes(String(req.query.unread_only || "").toLowerCase());
  const notifications = await listNotifications(req.user.id, { unreadOnly });
  res.json({ data: notifications });
}

export async function markRead(req, res) {
  const notification = await markNotificationAsRead(req.user.id, Number(req.params.id));

  if (!notification) {
    throw new ApiError(404, "notification_not_found", "Notification introuvable.");
  }

  res.json({ data: notification });
}

