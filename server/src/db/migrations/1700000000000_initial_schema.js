export const shorthands = undefined;

export async function up(pgm) {
  pgm.createType("user_role", ["student", "teacher", "validator", "admin"]);
  pgm.createType("request_status", ["pending", "approved", "refused", "provisioning", "provisioned", "failed", "expired", "destroyed"]);
  pgm.createType("vm_status", ["creating", "running", "stopped", "down", "expired", "destroyed", "error"]);
  pgm.createType("metric_state", ["up", "down", "unknown"]);
  pgm.createType("audit_severity", ["info", "success", "warning", "danger"]);

  pgm.createTable("users", {
    id: "id",
    full_name: { type: "varchar(120)", notNull: true },
    email: { type: "varchar(160)", notNull: true, unique: true },
    role: { type: "user_role", notNull: true },
    class_name: { type: "varchar(80)" },
    is_active: { type: "boolean", notNull: true, default: true },
    created_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") }
  });

  pgm.createTable("courses", {
    id: "id",
    name: { type: "varchar(120)", notNull: true },
    description: { type: "text" },
    teacher_id: { type: "integer", references: "users(id)", onDelete: "SET NULL" },
    created_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") }
  });

  pgm.createTable("vm_templates", {
    id: "id",
    course_id: { type: "integer", references: "courses(id)", onDelete: "CASCADE" },
    name: { type: "varchar(120)", notNull: true },
    description: { type: "text" },
    cpu: { type: "integer", notNull: true, check: "cpu > 0" },
    ram_gb: { type: "integer", notNull: true, check: "ram_gb > 0" },
    disk_gb: { type: "integer", notNull: true, check: "disk_gb > 0" },
    estimated_cost_per_hour_chf: { type: "numeric(8,4)", notNull: true, check: "estimated_cost_per_hour_chf >= 0" },
    ansible_playbook: { type: "varchar(160)", notNull: true },
    is_active: { type: "boolean", notNull: true, default: true }
  });

  pgm.createTable("vm_requests", {
    id: "id",
    requester_id: { type: "integer", notNull: true, references: "users(id)", onDelete: "RESTRICT" },
    course_id: { type: "integer", notNull: true, references: "courses(id)", onDelete: "RESTRICT" },
    template_id: { type: "integer", notNull: true, references: "vm_templates(id)", onDelete: "RESTRICT" },
    quantity: { type: "integer", notNull: true, default: 1, check: "quantity > 0" },
    start_date: { type: "date", notNull: true },
    end_date: { type: "date", notNull: true },
    status: { type: "request_status", notNull: true, default: "pending" },
    request_reason: { type: "text" },
    validator_id: { type: "integer", references: "users(id)", onDelete: "SET NULL" },
    decision_comment: { type: "text" },
    created_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") },
    updated_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") }
  });

  pgm.createTable("virtual_machines", {
    id: "id",
    request_id: { type: "integer", notNull: true, references: "vm_requests(id)", onDelete: "CASCADE" },
    owner_id: { type: "integer", notNull: true, references: "users(id)", onDelete: "RESTRICT" },
    provider_vm_id: { type: "varchar(120)" },
    name: { type: "varchar(120)", notNull: true },
    ip_address: { type: "varchar(60)" },
    status: { type: "vm_status", notNull: true, default: "creating" },
    ssh_username: { type: "varchar(80)", notNull: true, default: "student" },
    ssh_key_fingerprint: { type: "varchar(160)" },
    network_segment: { type: "varchar(80)" },
    created_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") },
    start_date: { type: "date", notNull: true },
    end_date: { type: "date", notNull: true },
    destroyed_at: { type: "timestamptz" }
  });

  pgm.createTable("vm_metrics", {
    id: "id",
    vm_id: { type: "integer", notNull: true, references: "virtual_machines(id)", onDelete: "CASCADE" },
    cpu_usage_percent: { type: "numeric(5,2)", check: "cpu_usage_percent IS NULL OR (cpu_usage_percent >= 0 AND cpu_usage_percent <= 100)" },
    ram_usage_percent: { type: "numeric(5,2)", check: "ram_usage_percent IS NULL OR (ram_usage_percent >= 0 AND ram_usage_percent <= 100)" },
    disk_usage_percent: { type: "numeric(5,2)", check: "disk_usage_percent IS NULL OR (disk_usage_percent >= 0 AND disk_usage_percent <= 100)" },
    state: { type: "metric_state", notNull: true, default: "unknown" },
    collected_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") }
  });

  pgm.createTable("cost_records", {
    id: "id",
    vm_id: { type: "integer", notNull: true, references: "virtual_machines(id)", onDelete: "CASCADE" },
    cost_date: { type: "date", notNull: true },
    hours_running: { type: "numeric(5,2)", notNull: true, check: "hours_running >= 0" },
    cost_estimate_chf: { type: "numeric(10,2)", notNull: true, check: "cost_estimate_chf >= 0" }
  });

  pgm.createTable("audit_events", {
    id: "id",
    actor_id: { type: "integer", references: "users(id)", onDelete: "SET NULL" },
    request_id: { type: "integer", references: "vm_requests(id)", onDelete: "SET NULL" },
    vm_id: { type: "integer", references: "virtual_machines(id)", onDelete: "SET NULL" },
    event_type: { type: "varchar(80)", notNull: true },
    severity: { type: "audit_severity", notNull: true, default: "info" },
    event_message: { type: "text", notNull: true },
    created_at: { type: "timestamptz", notNull: true, default: pgm.func("now()") }
  });

  pgm.createIndex("vm_requests", ["status"]);
  pgm.createIndex("virtual_machines", ["status"]);
  pgm.createIndex("vm_metrics", ["vm_id", "collected_at"]);
  pgm.createIndex("audit_events", ["event_type", "severity", "created_at"]);

  pgm.addConstraint("vm_requests", "vm_requests_end_after_start", "CHECK (end_date > start_date)");
  pgm.addConstraint(
    "vm_requests",
    "vm_requests_decision_fields",
    "CHECK (status NOT IN ('approved', 'refused') OR (validator_id IS NOT NULL AND decision_comment IS NOT NULL AND length(trim(decision_comment)) > 0))"
  );
  pgm.addConstraint("virtual_machines", "virtual_machines_end_after_start", "CHECK (end_date > start_date)");

  pgm.sql(`
    CREATE VIEW active_vm_costs AS
    SELECT
      vm.id AS vm_id,
      vm.name AS vm_name,
      vm.status,
      u.full_name AS owner_name,
      c.name AS course_name,
      t.name AS template_name,
      t.estimated_cost_per_hour_chf,
      vm.start_date,
      vm.end_date
    FROM virtual_machines vm
    JOIN users u ON u.id = vm.owner_id
    JOIN vm_requests r ON r.id = vm.request_id
    JOIN courses c ON c.id = r.course_id
    JOIN vm_templates t ON t.id = r.template_id
    WHERE vm.status IN ('creating', 'running', 'stopped', 'down');
  `);

  pgm.sql(`
    CREATE VIEW expiring_vms AS
    SELECT
      vm.id AS vm_id,
      vm.name AS vm_name,
      vm.status,
      u.full_name AS owner_name,
      vm.ip_address,
      vm.end_date
    FROM virtual_machines vm
    JOIN users u ON u.id = vm.owner_id
    WHERE vm.status IN ('running', 'stopped', 'down')
      AND vm.end_date <= (CURRENT_DATE + INTERVAL '2 days');
  `);
}

export async function down(pgm) {
  pgm.dropView("expiring_vms", { ifExists: true });
  pgm.dropView("active_vm_costs", { ifExists: true });
  pgm.dropTable("audit_events", { ifExists: true });
  pgm.dropTable("cost_records", { ifExists: true });
  pgm.dropTable("vm_metrics", { ifExists: true });
  pgm.dropTable("virtual_machines", { ifExists: true });
  pgm.dropTable("vm_requests", { ifExists: true });
  pgm.dropTable("vm_templates", { ifExists: true });
  pgm.dropTable("courses", { ifExists: true });
  pgm.dropTable("users", { ifExists: true });
  pgm.dropType("audit_severity", { ifExists: true });
  pgm.dropType("metric_state", { ifExists: true });
  pgm.dropType("vm_status", { ifExists: true });
  pgm.dropType("request_status", { ifExists: true });
  pgm.dropType("user_role", { ifExists: true });
}
