-- Donnees de test pour la demo

INSERT INTO users (id, full_name, email, role, class_name) VALUES
(1, 'Nadia Keller', 'nadia.keller@git.example', 'validator', NULL),
(2, 'Marc Dubois', 'marc.dubois@git.example', 'teacher', NULL),
(3, 'Amir Benali', 'amir.benali@git.example', 'student', 'IT-2026-A'),
(4, 'Sara Nguyen', 'sara.nguyen@git.example', 'student', 'IT-2026-A'),
(5, 'Leo Martin', 'leo.martin@git.example', 'student', 'IT-2026-B'),
(6, 'Josue App', 'josue.app@git.example', 'admin', NULL);

INSERT INTO courses (id, name, description, teacher_id) VALUES
(1, 'Administration Linux', 'Cours sur les bases Linux, SSH, services et droits.', 2),
(2, 'Developpement Web', 'Cours full-stack avec Git, Node.js et base de donnees.', 2),
(3, 'Data Science', 'Cours Python, notebooks, pandas et visualisation.', 2),
(4, 'Cybersecurity Lab', 'Cours reseau, durcissement et analyse de vulnerabilites.', 2);

INSERT INTO vm_templates (
    id,
    course_id,
    name,
    description,
    cpu,
    ram_gb,
    disk_gb,
    estimated_cost_per_hour_chf,
    ansible_playbook
) VALUES
(1, 1, 'Linux Admin', 'VM Ubuntu avec outils systeme et SSH.', 2, 4, 40, 0.0500, 'ansible/linux-admin.yml'),
(2, 2, 'Dev Web', 'VM avec Git, Node.js, Python et PostgreSQL client.', 2, 4, 60, 0.0600, 'ansible/dev-web.yml'),
(3, 3, 'Data Science', 'VM avec Python, Jupyter, pandas et scikit-learn.', 4, 8, 80, 0.1200, 'ansible/data-science.yml'),
(4, 4, 'Cybersecurity Lab', 'VM isolee avec outils de securite autorises.', 2, 4, 50, 0.0700, 'ansible/cybersecurity-lab.yml');

INSERT INTO vm_requests (
    id,
    requester_id,
    course_id,
    template_id,
    quantity,
    start_date,
    end_date,
    status,
    request_reason,
    validator_id,
    decision_comment
) VALUES
(1, 3, 1, 1, 1, '2026-06-17', '2026-06-24', 'provisioned', 'TP services Linux', 1, 'Demande conforme.'),
(2, 4, 2, 2, 1, '2026-06-18', '2026-06-25', 'approved', 'Projet web final', 1, 'OK pour le module.'),
(3, 2, 1, 1, 20, '2026-06-19', '2026-06-26', 'pending', 'Lot de VM pour la classe IT-2026-A', NULL, NULL),
(4, 5, 3, 3, 1, '2026-06-16', '2026-07-30', 'refused', 'Besoin personnel hors periode', 1, 'Duree trop longue pour le MVP.'),
(5, 3, 4, 4, 1, '2026-06-12', '2026-06-16', 'expired', 'Lab cyber court', 1, 'Expiree, destruction attendue.');

INSERT INTO virtual_machines (
    id,
    request_id,
    owner_id,
    provider_vm_id,
    name,
    ip_address,
    status,
    ssh_username,
    ssh_key_fingerprint,
    network_segment,
    start_date,
    end_date
) VALUES
(1, 1, 3, 'ik-vm-1001', 'git-linux-admin-amir-001', '10.10.1.21', 'running', 'student', 'SHA256:demo-amir', 'class-it-2026-a', '2026-06-17', '2026-06-24'),
(2, 5, 3, 'ik-vm-0991', 'git-cyber-amir-001', '10.10.4.12', 'expired', 'student', 'SHA256:demo-amir', 'class-it-2026-a', '2026-06-12', '2026-06-16');

INSERT INTO vm_metrics (id, vm_id, cpu_usage_percent, ram_usage_percent, disk_usage_percent, state, collected_at) VALUES
(1, 1, 12.50, 45.20, 31.00, 'up', '2026-06-16 10:00:00'),
(2, 1, 8.10, 42.70, 31.20, 'up', '2026-06-16 11:00:00'),
(3, 2, 0.20, 10.10, 25.00, 'down', '2026-06-16 11:00:00');

INSERT INTO cost_records (id, vm_id, cost_date, hours_running, cost_estimate_chf) VALUES
(1, 1, '2026-06-16', 8.00, 0.40),
(2, 2, '2026-06-16', 2.00, 0.14);

INSERT INTO audit_events (id, actor_id, request_id, vm_id, event_type, event_message) VALUES
(1, 3, 1, NULL, 'request_created', 'Amir a cree une demande Linux Admin.'),
(2, 1, 1, NULL, 'request_approved', 'Nadia a approuve la demande.'),
(3, NULL, 1, 1, 'vm_created', 'La VM git-linux-admin-amir-001 a ete creee.'),
(4, NULL, 1, 1, 'ansible_completed', 'Le playbook Linux Admin est termine.'),
(5, NULL, 5, 2, 'vm_expired', 'La VM git-cyber-amir-001 est arrivee a expiration.');

