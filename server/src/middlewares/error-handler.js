export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function notFoundHandler(req, res, next) {
  next(new ApiError(404, "not_found", `Route ${req.method} ${req.originalUrl} introuvable.`));
}

export function errorHandler(error, req, res, _next) {
  const status = error.status || 500;
  const code = error.code || "internal_error";
  const message = status === 500 ? "Erreur interne du serveur." : error.message;

  if (status === 500) {
    console.error(error);
  }

  res.status(status).json({
    error: {
      code,
      message
    }
  });
}
