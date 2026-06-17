import dotenv from "dotenv";

dotenv.config({ path: new URL("../../.env", import.meta.url) });
dotenv.config();

export const config = {
  nodeEnv: process.env.NODE_ENV || "development",
  port: Number(process.env.PORT || 3000),
  databaseUrl: process.env.DATABASE_URL,
  db: {
    host: process.env.PGHOST || "localhost",
    port: Number(process.env.PGPORT || 5432),
    user: process.env.PGUSER || "cloud_lab_dev",
    password: process.env.PGPASSWORD || "cloud_lab_dev_password",
    database: process.env.PGDATABASE || "cloud_lab"
  },
  session: {
    name: process.env.SESSION_COOKIE_NAME || "cloud_lab.sid",
    secret: process.env.SESSION_SECRET || "dev-only-change-me",
    maxAgeMs: Number(process.env.SESSION_MAX_AGE_MS || 1000 * 60 * 60 * 8)
  },
  auth: {
    mode: process.env.AUTH_MODE || "mock",
    azureTenantId: process.env.AZURE_TENANT_ID,
    azureClientId: process.env.AZURE_CLIENT_ID,
    azureClientSecret: process.env.AZURE_CLIENT_SECRET,
    azureRedirectUri: process.env.AZURE_REDIRECT_URI || "http://localhost:3000/api/v1/auth/callback",
    scopes: process.env.AZURE_SCOPES || "openid profile email User.Read"
  }
};
