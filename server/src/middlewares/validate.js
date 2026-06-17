import { ApiError } from "./error-handler.js";

export function validateBody(schema) {
  return (req, _res, next) => {
    const parsed = schema.safeParse(req.body);
    if (!parsed.success) {
      const message = parsed.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`).join("; ");
      next(new ApiError(400, "invalid_payload", message));
      return;
    }
    req.body = parsed.data;
    next();
  };
}
