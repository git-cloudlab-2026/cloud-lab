-- Schema data / monitoring / couts
-- Projet hackathon plateforme cloud GIT

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    role VARCHAR(30) NOT NULL CHECK (role IN ('student', 'teacher', 'validator', 'admin')),
    class_name VARCHAR(80),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    teacher_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vm_templates (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    name VARCHAR(120) NOT NULL,
    description TEXT,
    cpu INTEGER NOT NULL,
    ram_gb INTEGER NOT NULL,
    disk_gb INTEGER NOT NULL,
    estimated_cost_per_hour_chf DECIMAL(8, 4) NOT NULL,
    ansible_playbook VARCHAR(160) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE vm_requests (
    id INTEGER PRIMARY KEY,
    requester_id INTEGER NOT NULL REFERENCES users(id),
    course_id INTEGER NOT NULL REFERENCES courses(id),
    template_id INTEGER NOT NULL REFERENCES vm_templates(id),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL CHECK (
        status IN (
            'pending',
            'approved',
            'refused',
            'provisioning',
            'provisioned',
            'failed',
            'expired',
            'destroyed'
        )
    ),
    request_reason TEXT,
    validator_id INTEGER REFERENCES users(id),
    decision_comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date > start_date)
);

CREATE TABLE virtual_machines (
    id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES vm_requests(id),
    owner_id INTEGER NOT NULL REFERENCES users(id),
    provider_vm_id VARCHAR(120),
    name VARCHAR(120) NOT NULL,
    ip_address VARCHAR(60),
    status VARCHAR(30) NOT NULL CHECK (
        status IN (
            'creating',
            'running',
            'stopped',
            'down',
            'expired',
            'destroyed',
            'error'
        )
    ),
    ssh_username VARCHAR(80) NOT NULL DEFAULT 'student',
    ssh_key_fingerprint VARCHAR(160),
    network_segment VARCHAR(80),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    destroyed_at TIMESTAMP,
    CHECK (end_date > start_date)
);

CREATE TABLE vm_metrics (
    id INTEGER PRIMARY KEY,
    vm_id INTEGER NOT NULL REFERENCES virtual_machines(id),
    cpu_usage_percent DECIMAL(5, 2),
    ram_usage_percent DECIMAL(5, 2),
    disk_usage_percent DECIMAL(5, 2),
    state VARCHAR(20) NOT NULL CHECK (state IN ('up', 'down', 'unknown')),
    collected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cost_records (
    id INTEGER PRIMARY KEY,
    vm_id INTEGER NOT NULL REFERENCES virtual_machines(id),
    cost_date DATE NOT NULL,
    hours_running DECIMAL(5, 2) NOT NULL,
    cost_estimate_chf DECIMAL(10, 2) NOT NULL
);

CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    request_id INTEGER REFERENCES vm_requests(id),
    vm_id INTEGER REFERENCES virtual_machines(id),
    event_type VARCHAR(80) NOT NULL,
    event_message TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- VMs actives avec cout horaire
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

-- VMs qui expirent bientot
CREATE VIEW expiring_vms AS
SELECT
    vm.id AS vm_id,
    vm.name AS vm_name,
    vm.status,
    u.full_name AS owner_name,
    vm.end_date
FROM virtual_machines vm
JOIN users u ON u.id = vm.owner_id
WHERE vm.status IN ('running', 'stopped', 'down')
  AND vm.end_date <= DATE('now', '+2 day');

