"""Initial FastAPI schema.

Revision ID: 20260618_0001
Revises:
Create Date: 2026-06-18
"""

from alembic import op

revision = "20260618_0001"
down_revision = None
branch_labels = None
depends_on = None


def execute_batch(sql: str) -> None:
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement)


def upgrade() -> None:
    op.execute("CREATE TYPE user_role AS ENUM ('student', 'teacher', 'validator', 'admin')")
    op.execute("CREATE TYPE request_status AS ENUM ('pending', 'approved', 'refused', 'provisioning', 'provisioned', 'failed', 'expired', 'destroyed')")
    op.execute("CREATE TYPE vm_status AS ENUM ('creating', 'running', 'stopped', 'down', 'expired', 'destroyed', 'error')")
    op.execute("CREATE TYPE metric_state AS ENUM ('up', 'down', 'unknown')")
    op.execute("CREATE TYPE audit_severity AS ENUM ('info', 'success', 'warning', 'danger')")
    op.execute("CREATE TYPE notification_type AS ENUM ('vm_request_approved', 'vm_request_refused', 'vm_expiring_soon', 'vm_expired', 'vm_destroyed')")

    execute_batch(
        """
        CREATE TABLE users (
          id SERIAL PRIMARY KEY,
          full_name varchar(120) NOT NULL,
          email varchar(160) NOT NULL UNIQUE,
          role user_role NOT NULL,
          class_name varchar(80),
          is_active boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE courses (
          id SERIAL PRIMARY KEY,
          name varchar(120) NOT NULL,
          description text,
          teacher_id integer REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE vm_templates (
          id SERIAL PRIMARY KEY,
          course_id integer NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
          name varchar(120) NOT NULL,
          description text,
          cpu integer NOT NULL CHECK (cpu > 0),
          ram_gb integer NOT NULL CHECK (ram_gb > 0),
          disk_gb integer NOT NULL CHECK (disk_gb > 0),
          estimated_cost_per_hour_chf numeric(8,4) NOT NULL CHECK (estimated_cost_per_hour_chf >= 0),
          ansible_playbook varchar(160) NOT NULL,
          is_active boolean NOT NULL DEFAULT true
        );
        CREATE TABLE vm_requests (
          id SERIAL PRIMARY KEY,
          requester_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          course_id integer NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
          template_id integer NOT NULL REFERENCES vm_templates(id) ON DELETE RESTRICT,
          quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0),
          start_date date NOT NULL,
          end_date date NOT NULL CHECK (end_date > start_date),
          status request_status NOT NULL DEFAULT 'pending',
          request_reason text,
          validator_id integer REFERENCES users(id) ON DELETE SET NULL,
          decision_comment text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CHECK (status NOT IN ('approved', 'refused') OR (validator_id IS NOT NULL AND decision_comment IS NOT NULL AND length(trim(decision_comment)) > 0))
        );
        CREATE TABLE virtual_machines (
          id SERIAL PRIMARY KEY,
          request_id integer NOT NULL REFERENCES vm_requests(id) ON DELETE CASCADE,
          owner_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          provider_vm_id varchar(120),
          name varchar(120) NOT NULL,
          ip_address varchar(60),
          status vm_status NOT NULL DEFAULT 'creating',
          ssh_username varchar(80) NOT NULL DEFAULT 'student',
          ssh_key_fingerprint varchar(160),
          network_segment varchar(80),
          created_at timestamptz NOT NULL DEFAULT now(),
          start_date date NOT NULL,
          end_date date NOT NULL CHECK (end_date > start_date),
          destroyed_at timestamptz
        );
        CREATE TABLE vm_metrics (
          id SERIAL PRIMARY KEY,
          vm_id integer NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,
          cpu_usage_percent numeric(5,2) CHECK (cpu_usage_percent IS NULL OR cpu_usage_percent BETWEEN 0 AND 100),
          ram_usage_percent numeric(5,2) CHECK (ram_usage_percent IS NULL OR ram_usage_percent BETWEEN 0 AND 100),
          disk_usage_percent numeric(5,2) CHECK (disk_usage_percent IS NULL OR disk_usage_percent BETWEEN 0 AND 100),
          state metric_state NOT NULL DEFAULT 'unknown',
          collected_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE cost_records (
          id SERIAL PRIMARY KEY,
          vm_id integer NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,
          cost_date date NOT NULL,
          hours_running numeric(5,2) NOT NULL CHECK (hours_running >= 0),
          cost_estimate_chf numeric(10,2) NOT NULL CHECK (cost_estimate_chf >= 0)
        );
        CREATE TABLE audit_events (
          id SERIAL PRIMARY KEY,
          actor_id integer REFERENCES users(id) ON DELETE SET NULL,
          request_id integer REFERENCES vm_requests(id) ON DELETE SET NULL,
          vm_id integer REFERENCES virtual_machines(id) ON DELETE SET NULL,
          event_type varchar(80) NOT NULL,
          severity audit_severity NOT NULL DEFAULT 'info',
          event_message text NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE notifications (
          id SERIAL PRIMARY KEY,
          user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          type notification_type NOT NULL,
          title varchar(160) NOT NULL,
          message text NOT NULL,
          is_read boolean NOT NULL DEFAULT false,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_users_email ON users(email);
        CREATE INDEX ix_vm_requests_status ON vm_requests(status);
        CREATE INDEX ix_virtual_machines_status ON virtual_machines(status);
        CREATE INDEX ix_vm_metrics_vm_collected ON vm_metrics(vm_id, collected_at);
        CREATE INDEX ix_audit_events_filters ON audit_events(event_type, severity, created_at);
        CREATE VIEW expiring_vms AS
          SELECT vm.id AS vm_id, vm.name AS vm_name, vm.status, u.full_name AS owner_name, vm.ip_address, vm.end_date
          FROM virtual_machines vm
          JOIN users u ON u.id = vm.owner_id
          WHERE vm.status IN ('running', 'stopped', 'down')
            AND vm.end_date <= (CURRENT_DATE + INTERVAL '2 days');
        """
    )


def downgrade() -> None:
    execute_batch(
        """
        DROP VIEW IF EXISTS expiring_vms;
        DROP TABLE IF EXISTS notifications;
        DROP TABLE IF EXISTS audit_events;
        DROP TABLE IF EXISTS cost_records;
        DROP TABLE IF EXISTS vm_metrics;
        DROP TABLE IF EXISTS virtual_machines;
        DROP TABLE IF EXISTS vm_requests;
        DROP TABLE IF EXISTS vm_templates;
        DROP TABLE IF EXISTS courses;
        DROP TABLE IF EXISTS users;
        DROP TYPE IF EXISTS notification_type;
        DROP TYPE IF EXISTS audit_severity;
        DROP TYPE IF EXISTS metric_state;
        DROP TYPE IF EXISTS vm_status;
        DROP TYPE IF EXISTS request_status;
        DROP TYPE IF EXISTS user_role;
        """
    )
