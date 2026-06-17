import session from "express-session";
import connectPgSimple from "connect-pg-simple";
import { config } from "../config.js";
import { pool } from "../db/pool.js";

const PgSession = connectPgSimple(session);

export function sessionMiddleware() {
  return session({
    store: new PgSession({
      pool,
      tableName: "user_sessions",
      createTableIfMissing: true
    }),
    name: config.session.name,
    secret: config.session.secret,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      secure: config.nodeEnv === "production",
      maxAge: config.session.maxAgeMs
    }
  });
}

