import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal


def build_student_rows() -> str:
    rows: list[str] = []
    user_id = 100
    for class_index in range(1, 6):
        class_name = f"E{class_index}"
        for student_number in range(1, 26):
            full_name = f"Etudiant {class_name}-{student_number:02d}"
            email = f"e{class_index}.student{student_number:02d}@git.swiss"
            rows.append(f"({user_id}, '{full_name}', '{email}', 'student', '{class_name}')")
            user_id += 1
    return ",\n".join(rows)


STUDENT_ROWS = build_student_rows()

SEED_SQL = f"""
TRUNCATE TABLE notifications, audit_events, cost_records, vm_metrics, virtual_machines, vm_requests, vm_templates, courses, users RESTART IDENTITY CASCADE;

INSERT INTO users (id, full_name, email, role, class_name) VALUES
(1, 'Auguy Mabika', 'auguy.mabika@git.swiss', 'admin', NULL),
(2, 'Nadia Keller', 'nadia.keller@git.swiss', 'validator', NULL),
(3, 'Marc Dubois', 'marc.dubois@git.swiss', 'teacher', NULL),
(4, 'Josue Zongo', 'josue.zongo@git.swiss', 'admin', NULL),
(5, 'Lorenzo Mele', 'lorenzo.mele@git.swiss', 'teacher', NULL),
{STUDENT_ROWS};

INSERT INTO courses (id, name, description, teacher_id) VALUES
(1, 'Administration Linux', 'Cours sur les bases Linux, SSH, services et droits.', 3),
(2, 'Developpement Web', 'Cours full-stack avec Git, Node.js et base de donnees.', 3),
(3, 'Science des donnees', 'Cours Python, notebooks, pandas et visualisation.', 5),
(4, 'Laboratoire cybersecurite', 'Cours reseau, durcissement et analyse de vulnerabilites.', 5);

INSERT INTO vm_templates (id, course_id, name, description, cpu, ram_gb, disk_gb, estimated_cost_per_hour_chf, ansible_playbook) VALUES
(1, 1, 'Administration Linux', 'VM Ubuntu avec outils systeme et SSH.', 2, 4, 40, 0.0500, 'ansible/linux-admin.yml'),
(2, 2, 'Developpement Web', 'VM avec Git, Node.js, Python et PostgreSQL client.', 2, 4, 60, 0.0600, 'ansible/dev-web.yml'),
(3, 3, 'Science des donnees', 'VM avec Python, Jupyter, pandas et scikit-learn.', 4, 8, 80, 0.1200, 'ansible/data-science.yml'),
(4, 4, 'Laboratoire cybersecurite', 'VM isolee avec outils de securite autorises.', 2, 4, 50, 0.0700, 'ansible/cybersecurity-lab.yml');
"""

DEMO_SQL = """
INSERT INTO vm_requests (id, requester_id, course_id, template_id, quantity, start_date, end_date, status, request_reason, validator_id, decision_comment) VALUES
(1, 100, 1, 1, 1, '2026-06-17', '2026-06-24', 'provisioned', 'TP services Linux', 2, 'Demande conforme.'),
(2, 101, 2, 2, 1, '2026-06-18', '2026-06-25', 'approved', 'Projet web final', 2, 'OK pour le module.'),
(3, 3, 1, 1, 25, '2026-06-19', '2026-06-26', 'pending', 'Lot de VM pour la classe E1', NULL, NULL),
(4, 150, 3, 3, 1, '2026-06-16', '2026-07-30', 'refused', 'Besoin personnel hors periode', 2, 'Duree trop longue pour le pilote.'),
(5, 102, 4, 4, 1, '2026-06-12', '2026-06-16', 'expired', 'Lab cyber court', 2, 'Expiree, destruction attendue.');

INSERT INTO virtual_machines (id, request_id, owner_id, provider_vm_id, name, ip_address, status, ssh_username, ssh_key_fingerprint, network_segment, start_date, end_date) VALUES
(1, 1, 100, 'ik-vm-1001', 'git-linux-e1-01-001', '10.10.1.21', 'running', 'student', 'SHA256:demo-e1-01', 'class-e1', '2026-06-17', '2026-06-24'),
(2, 5, 102, 'ik-vm-0991', 'git-cyber-e1-03-001', '10.10.4.12', 'expired', 'student', 'SHA256:demo-e1-03', 'class-e1', '2026-06-12', '2026-06-16');

INSERT INTO vm_metrics (id, vm_id, cpu_usage_percent, ram_usage_percent, disk_usage_percent, state, collected_at) VALUES
(1, 1, 12.50, 45.20, 31.00, 'up', '2026-06-16 10:00:00+02'),
(2, 1, 8.10, 42.70, 31.20, 'up', '2026-06-16 11:00:00+02'),
(3, 2, 0.20, 10.10, 25.00, 'down', '2026-06-16 11:00:00+02');

INSERT INTO cost_records (id, vm_id, cost_date, hours_running, cost_estimate_chf) VALUES
(1, 1, '2026-06-16', 8.00, 0.40),
(2, 2, '2026-06-16', 2.00, 0.14);

INSERT INTO audit_events (id, actor_id, request_id, vm_id, event_type, severity, event_message) VALUES
(1, 100, 1, NULL, 'request_created', 'success', 'Un etudiant E1 a cree une demande Linux Admin.'),
(2, 2, 1, NULL, 'request_approved', 'success', 'Nadia a approuve la demande.'),
(3, NULL, 1, 1, 'vm_created', 'success', 'La VM git-linux-e1-01-001 a ete creee.'),
(4, NULL, 1, 1, 'ansible_completed', 'success', 'Le playbook Linux Admin est termine.'),
(5, NULL, 5, 2, 'vm_expired', 'warning', 'La VM git-cyber-e1-03-001 est arrivee a expiration.');
"""

SEQUENCES_SQL = """
SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1), true);
SELECT setval(pg_get_serial_sequence('courses', 'id'), COALESCE((SELECT MAX(id) FROM courses), 1), true);
SELECT setval(pg_get_serial_sequence('vm_templates', 'id'), COALESCE((SELECT MAX(id) FROM vm_templates), 1), true);
SELECT setval(pg_get_serial_sequence('vm_requests', 'id'), COALESCE((SELECT MAX(id) FROM vm_requests), 1), true);
SELECT setval(pg_get_serial_sequence('virtual_machines', 'id'), COALESCE((SELECT MAX(id) FROM virtual_machines), 1), true);
SELECT setval(pg_get_serial_sequence('vm_metrics', 'id'), COALESCE((SELECT MAX(id) FROM vm_metrics), 1), true);
SELECT setval(pg_get_serial_sequence('cost_records', 'id'), COALESCE((SELECT MAX(id) FROM cost_records), 1), true);
SELECT setval(pg_get_serial_sequence('audit_events', 'id'), COALESCE((SELECT MAX(id) FROM audit_events), 1), true);
SELECT setval(pg_get_serial_sequence('notifications', 'id'), COALESCE((SELECT MAX(id) FROM notifications), 1), true);
"""


async def main() -> None:
    settings = get_settings()
    load_demo_data = not (settings.provisioner_mode in {"openstack", "terraform"} and settings.real_provisioning_enabled)
    sql = SEED_SQL
    if load_demo_data:
        sql += DEMO_SQL
    sql += SEQUENCES_SQL

    async with SessionLocal() as session:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                await session.execute(text(statement))
        await session.commit()
    mode = "avec donnees demo" if load_demo_data else "sans VM demo en mode provisioning reel"
    print(f"Seed PostgreSQL termine: 5 classes E1-E5, 25 eleves par classe, {mode}.")


if __name__ == "__main__":
    asyncio.run(main())
