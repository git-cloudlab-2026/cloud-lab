import dotenv from "dotenv";

dotenv.config({ path: new URL("../../.env", import.meta.url) });
dotenv.config();

export const config = {
  port: Number(process.env.PORT || 3000),
  databaseUrl: process.env.DATABASE_URL,
  db: {
    host: process.env.PGHOST || "localhost",
    port: Number(process.env.PGPORT || 5432),
    user: process.env.PGUSER || "cloud_lab_dev",
    password: process.env.PGPASSWORD || "cloud_lab_dev_password",
    database: process.env.PGDATABASE || "cloud_lab"
  }
};
