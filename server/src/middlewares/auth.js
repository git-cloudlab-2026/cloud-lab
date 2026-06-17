import { query } from "../db/pool.js";
import { ApiError } from "./error-handler.js";

const userFields = "id, full_name, email, role, class_name, is_active, created_at";

export async function attachCurrentUser(req, _res, next) {
  try {
    const userId = req.session?.userId;
    if (!userId) {
      req.user = null;
      next();
      return;
    }

    const { rows } = await query(`SELECT ${userFields} FROM users WHERE id = $1 AND is_active = true`, [userId]);
    req.user = rows[0] || null;

    if (!req.user && req.session) {
      req.session.userId = null;
    }

    next();
  } catch (error) {
    next(error);
  }
}

export function requireAuth(req, _res, next) {
  if (!req.user) {
    next(new ApiError(401, "authentication_required", "Authentification requise."));
    return;
  }
  next();
}

export function requireRole(...roles) {
  return (req, _res, next) => {
    if (!req.user) {
      next(new ApiError(401, "authentication_required", "Authentification requise."));
      return;
    }

    if (!roles.includes(req.user.role)) {
      next(new ApiError(403, "insufficient_role", `Role requis: ${roles.join(", ")}.`));
      return;
    }

    next();
  };
}

