export const shorthands = undefined;

export async function up(pgm) {
  pgm.createTable("notifications", {
    id: "id",
    user_id: { type: "integer", notNull: true, references: "users(id)", onDelete: "CASCADE" },
    type: { type: "varchar(80)", notNull: true },
    title: { type: "varchar(160)", notNull: true },
    message: { type: "text", notNull: true },
    is_read: { type: "boolean", notNull: true, default: false },
    metadata: { type: "jsonb", notNull: true, default: pgm.func("'{}'::jsonb") },
    created_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") }
  });

  pgm.createIndex("notifications", ["user_id", "is_read", "created_at"]);
  pgm.createIndex("notifications", ["type", "created_at"]);
}

export async function down(pgm) {
  pgm.dropTable("notifications", { ifExists: true });
}
