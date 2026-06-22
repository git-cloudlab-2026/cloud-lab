/*
  Couche DATA - Cloud Lab Control Center

  Schema choisi:
  - users: personnes qui demandent ou valident les VM (student, trainer, validator, admin)
  - courses: cours/modules relies aux templates et aux couts
  - templates: source unique de verite du catalogue (flavor, image, outils, cout/h)
  - requests: demandes de VM avec timestamps de cycle de vie
  - vms: machines virtuelles provisionnees ou pilotees
  - events: journal d'audit lisible pendant la demo

  State machine officielle:
  pending -> approved -> provisioning -> active -> expiring -> expired -> destroyed
  Une transition vers error est autorisee depuis les etapes techniques.

  Pourquoi ce choix:
  - les statuts sont previsibles pour le portail, l'infra et le dashboard;
  - chaque transition garde un timestamp exploitable;
  - le cout estime est calcule a la demande, le cout reel a partir de la duree d'usage;
  - les prix ne sont pas poses au hasard: ils partent d'une reference publique Infomaniak
    4 CPU / 8 GB RAM / 50 GB stockage = 16.10 CHF/mois, hors TVA, puis sont proratises
    selon CPU/RAM/disque et convertis en cout horaire;
  - Authentification OIDC reelle cote backend FastAPI. Le front redirige vers
    /api/v1/auth/login en mode production. Le mode mock reste disponible uniquement
    pour developper sans tenant Microsoft.
  - les fonctions query.* evitent de dupliquer la logique dans chaque vue.
*/

const STORAGE_KEY = "git-cloud-lab-control-center-v4";
const CLOCK_NOW = "2026-06-17T10:00:00";
const EXPIRING_THRESHOLD_HOURS = 24;
const DATA_MODE = "mock"; // "api" = FastAPI/PostgreSQL, "local" = fallback statique.
const AUTH_MODE_FRONT = "mock"; // Le backend peut rester en AUTH_MODE=mock pendant le developpement.
const API_ORIGIN = window.location.protocol.startsWith("http") && window.location.port === "8000"
  ? window.location.origin
  : "http://localhost:8000";
const API_BASE_URL = `${API_ORIGIN}/api/v1`;
const API_DEV_LOGIN_USER_ID = 1;
const AUTH_TOKEN_KEY = "cloudLabAccessToken";

if (new URLSearchParams(window.location.search).has("resetSession")) {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  window.history.replaceState(null, "", window.location.pathname);
}

if (DATA_MODE === "api" && window.location.protocol === "file:") {
  window.location.replace(`${API_ORIGIN}/portal/`);
}

const ROLE_LABELS = {
  student: "Étudiant",
  trainer: "Formateur",
  validator: "Validateur",
  admin: "Admin"
};

const PERMISSIONS = {
  approveRequest: ["validator", "admin"],
  refuseRequest: ["validator", "admin"],
  provisionVm: ["validator", "admin"],
  destroyExpiredVms: ["admin"],
  resetData: ["admin"],
  exportCsv: ["student", "trainer", "validator", "admin"],
  createGroupRequest: ["trainer", "validator", "admin"],
  viewAudit: ["validator", "admin"],
  createForOtherUser: ["validator", "admin"]
};

// Regles de navigation explicites par role. La vue validation sert aussi de
// "Mes demandes" pour student/trainer, mais les actions restent bloquees par PERMISSIONS.
const VIEW_ACCESS = {
  dashboard: ["student", "trainer", "validator", "admin"],
  catalog: ["student", "trainer", "validator", "admin"],
  request: ["student", "trainer", "validator", "admin"],
  validation: ["student", "trainer", "validator", "admin"],
  vms: ["student", "trainer", "validator", "admin"],
  audit: ["validator", "admin"],
  login: []
};

const PRICING_MODEL = {
  provider: "Infomaniak Public Cloud",
  sourceLabel: "Reference publique Infomaniak: 4 CPU / 8 GB RAM / 50 GB = 16.10 CHF/mois, hors TVA",
  referenceMonthlyChf: 16.10,
  referenceCpu: 4,
  referenceRamGb: 8,
  referenceDiskGb: 50,
  billingHoursPerMonth: 730,
  weights: {
    cpu: 0.45,
    ram: 0.35,
    disk: 0.20
  }
};

const STATUS_ORDER = ["pending", "approved", "provisioning", "active", "expiring", "expired", "destroyed"];
const VALID_TRANSITIONS = {
  pending: ["approved", "refused", "error"],
  approved: ["provisioning", "refused", "error"],
  provisioning: ["active", "error", "expired"],
  active: ["expiring", "expired", "error"],
  expiring: ["expired", "destroyed", "error"],
  expired: ["destroyed", "error"],
  destroyed: [],
  refused: [],
  error: ["provisioning", "destroyed"]
};

const seed = {
  users: [
    { id: 1, fullName: "Nadia Keller", email: "nadia.keller@git.swiss", role: "validator", className: "", provider: "entra-mock", entraObjectId: "mock-nadia-keller", lastLoginAt: null },
    { id: 2, fullName: "Marc Dubois", email: "marc.dubois@git.swiss", role: "trainer", className: "E1", provider: "entra-mock", entraObjectId: "mock-marc-dubois", lastLoginAt: null },
    { id: 3, fullName: "Amir Benali", email: "amir.benali@git.swiss", role: "student", className: "E1", provider: "entra-mock", entraObjectId: "mock-amir-benali", lastLoginAt: null },
    { id: 4, fullName: "Sara Nguyen", email: "sara.nguyen@git.swiss", role: "student", className: "E1", provider: "entra-mock", entraObjectId: "mock-sara-nguyen", lastLoginAt: null },
    { id: 5, fullName: "Leo Martin", email: "leo.martin@git.swiss", role: "student", className: "E2", provider: "entra-mock", entraObjectId: "mock-leo-martin", lastLoginAt: null },
    { id: 6, fullName: "Administrateur Lab", email: "admin@git.swiss", role: "admin", className: "", provider: "entra-mock", entraObjectId: "mock-admin-lab", lastLoginAt: null }
  ],
  currentUser: null,
  courses: [
    { id: 1, slug: "linux-admin", name: "Administration Linux", className: "IT-2026-A", budgetChf: 160 },
    { id: 2, slug: "dev-web", name: "Développement Web", className: "IT-2026-A", budgetChf: 180 },
    { id: 3, slug: "data-science", name: "Science des données", className: "IT-2026-B", budgetChf: 260 },
    { id: 4, slug: "securite", name: "Laboratoire cybersécurité", className: "IT-2026-C", budgetChf: 220 }
  ],
  templates: [
    {
      id: 1,
      slug: "linux-admin",
      courseId: 1,
      name: "Administration Linux",
      description: "Ubuntu LTS avec outils système, SSH sécurisé et nginx.",
      flavor: { name: "lab.small", cpu: 2, ramGb: 4, diskGb: 40 },
      image: "ubuntu-22.04-lts",
      tools: ["bash", "vim", "systemd", "nginx", "ufw"],
      hourlyCostChf: 0.052,
      playbook: "ansible/linux-admin.yml"
    },
    {
      id: 2,
      slug: "dev-web",
      courseId: 2,
      name: "Développement Web",
      description: "Environnement Git, Node.js, Python et outils web.",
      flavor: { name: "lab.small-plus", cpu: 2, ramGb: 4, diskGb: 60 },
      image: "ubuntu-22.04-lts",
      tools: ["git", "nodejs", "python", "postgresql-client"],
      hourlyCostChf: 0.064,
      playbook: "ansible/dev-web.yml"
    },
    {
      id: 3,
      slug: "data-science",
      courseId: 3,
      name: "Science des données",
      description: "Python, Jupyter, pandas, scikit-learn et notebooks.",
      flavor: { name: "lab.medium", cpu: 4, ramGb: 8, diskGb: 80 },
      image: "ubuntu-22.04-lts",
      tools: ["python", "jupyter", "pandas", "scikit-learn"],
      hourlyCostChf: 0.128,
      playbook: "ansible/data-science.yml"
    },
    {
      id: 4,
      slug: "securite",
      courseId: 4,
      name: "Laboratoire cybersécurité",
      description: "VM isolée avec outils sécurité autorisés pour laboratoire.",
      flavor: { name: "lab.security", cpu: 2, ramGb: 4, diskGb: 50 },
      image: "ubuntu-22.04-lts-isolated",
      tools: ["nmap", "tcpdump", "wireshark-cli", "fail2ban"],
      hourlyCostChf: 0.074,
      playbook: "ansible/cybersecurity-lab.yml"
    }
  ],
  requests: [
    {
      id: 1,
      requesterId: 3,
      courseId: 1,
      templateId: 1,
      quantity: 1,
      startDate: "2026-06-14",
      endDate: "2026-06-20",
      status: "active",
      reason: "TP services Linux",
      validatorId: 1,
      decisionComment: "Demande conforme.",
      createdAt: "2026-06-13T09:12:00",
      approvedAt: "2026-06-13T10:03:00",
      provisioningAt: "2026-06-13T10:08:00",
      provisionedAt: "2026-06-13T10:14:00",
      destroyedAt: null
    },
    {
      id: 2,
      requesterId: 4,
      courseId: 2,
      templateId: 2,
      quantity: 1,
      startDate: "2026-06-18",
      endDate: "2026-06-25",
      status: "approved",
      reason: "Projet web final",
      validatorId: 1,
      decisionComment: "OK pour le module.",
      createdAt: "2026-06-16T11:22:00",
      approvedAt: "2026-06-16T13:40:00",
      provisioningAt: null,
      provisionedAt: null,
      destroyedAt: null
    },
    {
      id: 3,
      requesterId: 2,
      courseId: 1,
      templateId: 1,
      quantity: 20,
      startDate: "2026-06-19",
      endDate: "2026-06-26",
      status: "pending",
      reason: "Lot de VM pour la classe IT-2026-A",
      validatorId: null,
      decisionComment: "",
      createdAt: "2026-06-17T08:20:00",
      approvedAt: null,
      provisioningAt: null,
      provisionedAt: null,
      destroyedAt: null
    },
    {
      id: 4,
      requesterId: 5,
      courseId: 3,
      templateId: 3,
      quantity: 1,
      startDate: "2026-06-16",
      endDate: "2026-07-30",
      status: "refused",
      reason: "Besoin personnel hors periode",
      validatorId: 1,
      decisionComment: "Durée trop longue pour le pilote.",
      createdAt: "2026-06-16T09:45:00",
      approvedAt: null,
      provisioningAt: null,
      provisionedAt: null,
      destroyedAt: null
    },
    {
      id: 5,
      requesterId: 3,
      courseId: 4,
      templateId: 4,
      quantity: 1,
      startDate: "2026-06-12",
      endDate: "2026-06-16",
      status: "expired",
      reason: "Lab cyber court",
      validatorId: 1,
      decisionComment: "Expiree, destruction attendue.",
      createdAt: "2026-06-11T14:08:00",
      approvedAt: "2026-06-11T15:10:00",
      provisioningAt: "2026-06-11T15:16:00",
      provisionedAt: "2026-06-11T15:24:00",
      destroyedAt: null
    },
    {
      id: 6,
      requesterId: 5,
      courseId: 3,
      templateId: 3,
      quantity: 1,
      startDate: "2026-06-16",
      endDate: "2026-06-18",
      status: "expiring",
      reason: "Notebook Jupyter pour analyse de donnees",
      validatorId: 1,
      decisionComment: "OK, durée courte et coût maîtrisé.",
      createdAt: "2026-06-15T16:20:00",
      approvedAt: "2026-06-15T16:44:00",
      provisioningAt: "2026-06-16T08:10:00",
      provisionedAt: "2026-06-16T08:18:00",
      destroyedAt: null
    },
    {
      id: 7,
      requesterId: 4,
      courseId: 2,
      templateId: 2,
      quantity: 1,
      startDate: "2026-06-10",
      endDate: "2026-06-12",
      status: "destroyed",
      reason: "Revision projet web",
      validatorId: 1,
      decisionComment: "Environnement fermé après échéance.",
      createdAt: "2026-06-09T15:30:00",
      approvedAt: "2026-06-09T16:00:00",
      provisioningAt: "2026-06-10T09:03:00",
      provisionedAt: "2026-06-10T09:11:00",
      destroyedAt: "2026-06-12T18:05:00"
    },
    {
      id: 8,
      requesterId: 3,
      courseId: 1,
      templateId: 1,
      quantity: 1,
      startDate: "2026-06-17",
      endDate: "2026-06-19",
      status: "error",
      reason: "Test de reprise après erreur de provisionnement",
      validatorId: 1,
      decisionComment: "Erreur conservée pour démontrer le suivi.",
      createdAt: "2026-06-17T07:35:00",
      approvedAt: "2026-06-17T07:42:00",
      provisioningAt: "2026-06-17T07:48:00",
      provisionedAt: null,
      destroyedAt: null
    }
  ],
  vms: [
    {
      id: 1,
      requestId: 1,
      ownerId: 3,
      providerVmId: "ik-vm-1001",
      name: "git-linux-admin-amir-001",
      ip: "10.10.1.21",
      status: "active",
      sshUser: "student",
      sshKey: "SHA256:lab-amir",
      network: "class-it-2026-a",
      createdAt: "2026-06-13T10:08:00",
      provisionedAt: "2026-06-13T10:14:00",
      startDate: "2026-06-14",
      endDate: "2026-06-20",
      destroyedAt: null
    },
    {
      id: 2,
      requestId: 5,
      ownerId: 3,
      providerVmId: "ik-vm-0991",
      name: "git-cyber-amir-001",
      ip: "10.10.4.12",
      status: "expired",
      sshUser: "student",
      sshKey: "SHA256:lab-amir",
      network: "class-it-2026-a",
      createdAt: "2026-06-11T15:16:00",
      provisionedAt: "2026-06-11T15:24:00",
      startDate: "2026-06-12",
      endDate: "2026-06-16",
      destroyedAt: null
    },
    {
      id: 3,
      requestId: 6,
      ownerId: 5,
      providerVmId: "ik-vm-1012",
      name: "git-data-science-leo-003",
      ip: "10.10.3.23",
      status: "expiring",
      sshUser: "student",
      sshKey: "SHA256:lab-leo",
      network: "class-it-2026-b",
      createdAt: "2026-06-16T08:10:00",
      provisionedAt: "2026-06-16T08:18:00",
      startDate: "2026-06-16",
      endDate: "2026-06-18",
      destroyedAt: null
    },
    {
      id: 4,
      requestId: 7,
      ownerId: 4,
      providerVmId: "ik-vm-0877",
      name: "git-dev-web-sara-004",
      ip: "10.10.2.24",
      status: "destroyed",
      sshUser: "student",
      sshKey: "SHA256:lab-sara",
      network: "class-it-2026-a",
      createdAt: "2026-06-10T09:03:00",
      provisionedAt: "2026-06-10T09:11:00",
      startDate: "2026-06-10",
      endDate: "2026-06-12",
      destroyedAt: "2026-06-12T18:05:00"
    },
    {
      id: 5,
      requestId: 8,
      ownerId: 3,
      providerVmId: "ik-vm-1020",
      name: "git-linux-admin-amir-005",
      ip: "10.10.1.25",
      status: "error",
      sshUser: "student",
      sshKey: "SHA256:lab-amir",
      network: "class-it-2026-a",
      createdAt: "2026-06-17T07:48:00",
      provisionedAt: null,
      startDate: "2026-06-17",
      endDate: "2026-06-19",
      destroyedAt: null
    }
  ],
  events: [
    "2026-06-17 08:20 - Demande groupée Linux Admin enregistrée.",
    "2026-06-16 13:40 - Demande développement web approuvée.",
    "2026-06-13 10:14 - VM git-linux-admin-amir-001 active.",
    "2026-06-11 15:24 - VM git-cyber-amir-001 provisionnée.",
    "2026-06-16 00:00 - VM git-cyber-amir-001 arrivée à expiration."
  ]
};

let state = normaliseState(loadState());
refreshLifecycleStatuses();

function loadState() {
  if (DATA_MODE === "api") return structuredClone(seed);
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return structuredClone(seed);
  try {
    return JSON.parse(raw);
  } catch {
    return structuredClone(seed);
  }
}

function saveState() {
  if (DATA_MODE === "api") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

async function apiRequest(path, options = {}) {
  const { skipAuth = false, headers: optionHeaders = {}, ...fetchOptions } = options;
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const headers = {
    "Content-Type": "application/json",
    ...(!skipAuth && token ? { Authorization: `Bearer ${token}` } : {}),
    ...optionHeaders
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers,
    ...fetchOptions
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.message || payload?.error?.message || payload?.detail || `Erreur API ${response.status}`;
    throw new Error(message);
  }
  return payload?.data ?? payload;
}

async function credentialLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector(".credential-submit");
  const email = document.querySelector("#credentialEmail").value.trim().toLowerCase();
  const password = document.querySelector("#credentialPassword").value;

  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = "Connexion...";
  try {
    const session = await apiRequest("/auth/login", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ email, password })
    });

    localStorage.setItem(AUTH_TOKEN_KEY, session.access_token);
    state.currentUser = buildAuthUser(mapApiUser(session.user));
    await hydrateFromApi();
    renderAll();
    setView("dashboard");
  } catch (error) {
    alert(`Connexion impossible: ${error.message}`);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Se connecter";
  }
}

function mapApiRole(role) {
  if (role === "teacher") return "trainer";
  return role;
}

function mapApiStatus(status) {
  const map = {
    running: "active",
    stopped: "expired",
    down: "error"
  };
  return map[status] || status;
}

function mapFrontendVmStatus(status) {
  const map = {
    active: "running",
    expiring: "running",
    expired: "expired",
    destroyed: "destroyed",
    error: "down"
  };
  return map[status] || status;
}

function mapApiUser(user) {
  const role = mapApiRole(user.role);
  return {
    id: user.id,
    fullName: user.full_name,
    email: user.email,
    role,
    className: user.class_name || "",
    provider: "entra-id",
    entraObjectId: `api-user-${user.id}`,
    lastLoginAt: user.created_at || null
  };
}

function mapApiCourse(course, index) {
  const fallback = seed.courses[index % seed.courses.length] || {};
  return {
    id: course.id,
    slug: fallback.slug || `course-${course.id}`,
    name: course.name,
    className: fallback.className || "E1-E5",
    budgetChf: fallback.budgetChf || 200,
    description: course.description || ""
  };
}

function mapApiTemplate(template) {
  const fallbackSlug = template.name.toLowerCase().replaceAll(" ", "-");
  return {
    id: template.id,
    slug: fallbackSlug,
    courseId: template.course_id,
    name: template.name,
    description: template.description || "",
    flavor: {
      name: `lab.${template.cpu}c-${template.ram_gb}g`,
      cpu: template.cpu,
      ramGb: template.ram_gb,
      diskGb: template.disk_gb
    },
    image: "ubuntu-22.04-lts",
    tools: [],
    hourlyCostChf: Number(template.estimated_cost_per_hour_chf || 0),
    playbook: template.ansible_playbook || ""
  };
}

function mapApiRequest(request) {
  return {
    id: request.id,
    requesterId: request.requester_id,
    courseId: request.course_id,
    templateId: request.template_id,
    quantity: request.quantity,
    startDate: request.start_date,
    endDate: request.end_date,
    status: mapApiStatus(request.status),
    reason: request.request_reason || "",
    validatorId: request.validator_id,
    decisionComment: request.decision_comment || "",
    createdAt: request.created_at,
    approvedAt: request.status === "approved" ? request.updated_at : null,
    provisioningAt: request.status === "provisioning" ? request.updated_at : null,
    provisionedAt: null,
    destroyedAt: null
  };
}

function mapApiVm(vm) {
  return {
    id: vm.id,
    requestId: vm.request_id,
    ownerId: vm.owner_id,
    providerVmId: vm.provider_vm_id,
    name: vm.name,
    ip: vm.ip_address || "-",
    status: mapApiStatus(vm.status),
    sshUser: vm.ssh_username || "student",
    sshKey: vm.ssh_key_fingerprint || "",
    network: normaliseNetworkSegment(vm.network_segment),
    createdAt: vm.created_at,
    provisionedAt: vm.created_at,
    startDate: vm.start_date,
    endDate: vm.end_date,
    destroyedAt: vm.destroyed_at
  };
}

function mapApiAuditEvent(event) {
  return {
    id: event.id,
    at: event.created_at,
    actorId: event.actor_id,
    actorName: byId(state.users, event.actor_id)?.fullName || "Systeme",
    actorEmail: byId(state.users, event.actor_id)?.email || "",
    actorRole: byId(state.users, event.actor_id)?.role || "system",
    type: event.event_type,
    severity: event.severity,
    targetType: event.vm_id ? "vm" : event.request_id ? "request" : "-",
    targetId: event.vm_id || event.request_id || "-",
    scope: "-",
    detail: event.event_message
  };
}

async function hydrateFromApi() {
  const [users, courses, templates, requests, vms, auditEvents, notifications, dashboardSummary] = await Promise.all([
    apiRequest("/users"),
    apiRequest("/courses"),
    apiRequest("/vm-templates"),
    apiRequest("/vm-requests"),
    apiRequest("/virtual-machines"),
    apiRequest("/audit-events"),
    apiRequest("/notifications"),
    apiRequest("/dashboard/summary")
  ]);

  state.users = users.map(mapApiUser);
  state.courses = courses.map(mapApiCourse);
  state.templates = templates.map(mapApiTemplate);
  state.requests = requests.map(mapApiRequest);
  state.vms = vms.map(mapApiVm);
  state.events = auditEvents.map(mapApiAuditEvent);
  state.notifications = notifications;
  state.dashboardSummary = dashboardSummary;
  state = normaliseState(state);
}

async function refreshFromApiAndRender() {
  if (DATA_MODE !== "api") {
    renderAll();
    return;
  }
  try {
    await hydrateFromApi();
  } catch (error) {
    console.error(error);
    alert(`Impossible de synchroniser avec l'API: ${error.message}`);
  }
  renderAll();
}

function normaliseState(input) {
  const data = structuredClone(input);
  const sessionUser = data.currentUser;
  data.users ||= [];
  data.courses ||= [];
  data.templates ||= [];
  data.requests ||= [];
  data.vms ||= [];
  data.events ||= [];
  // En mode local, la session n'est pas restauree depuis localStorage. En mode API,
  // elle vient exclusivement de /auth/me et peut donc etre conservee pendant le rendu.
  data.currentUser = DATA_MODE === "api" && sessionUser ? sessionUser : null;

  data.users.forEach((user) => {
    user.provider ||= "entra-mock";
    user.entraObjectId ||= `mock-${user.fullName.toLowerCase().replaceAll(" ", "-")}`;
    user.lastLoginAt ||= null;
  });

  data.templates.forEach((template) => {
    template.pricing = computeTemplatePricing(template);
    template.hourlyCostChf = template.pricing.hourlyChf;
    template.monthlyCostChf = template.pricing.monthlyChf;
  });

  data.requests.forEach((request) => {
    request.createdAt ||= `${request.startDate}T08:00:00`;
    request.approvedAt ||= request.status === "approved" || request.status === "active" ? request.createdAt : null;
    request.provisioningAt ||= null;
    request.provisionedAt ||= request.status === "active" ? request.approvedAt : null;
    request.destroyedAt ||= null;
    if (request.status === "provisioned") request.status = "active";
  });

  data.vms.forEach((vm) => {
    vm.createdAt ||= `${vm.startDate}T08:00:00`;
    vm.provisionedAt ||= vm.createdAt;
    vm.destroyedAt ||= null;
    vm.network = normaliseNetworkSegment(vm.network);
    if (vm.status === "running") vm.status = "active";
  });

  data.events = data.events.map((event, index) => normaliseAuditEvent(event, index));

  return data;
}

function normaliseNetworkSegment(network) {
  if (!network) return "class-course-unknown";
  if (network.startsWith("class-")) return network;
  if (network.startsWith("course-")) return `class-${network}`;
  return `class-${network}`;
}

function byId(list, id) {
  return list.find((item) => item.id === Number(id));
}

function buildAuthUser(user) {
  return {
    id: user.id,
    fullName: user.fullName,
    email: user.email,
    role: user.role,
    className: user.className,
    provider: user.provider || "entra-mock",
    entraObjectId: user.entraObjectId,
    claims: {
      name: user.fullName,
      preferred_username: user.email,
      oid: user.entraObjectId,
      roles: [user.role]
    }
  };
}

function currentUser() {
  return state.currentUser;
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role || "Invité";
}

function can(action, user = currentUser()) {
  return PERMISSIONS[action]?.includes(user?.role) ?? false;
}

function requirePermission(action) {
  if (can(action)) return true;
  addEvent("permission_denied", `Action non autorisée: ${action}.`, {
    severity: "warning",
    targetType: "permission",
    targetId: action
  });
  alert("Action non autorisée pour votre rôle.");
  saveState();
  renderEvents();
  renderAudit();
  return false;
}

function normaliseAuditEvent(event, index) {
  if (typeof event === "object" && event.type) {
    return {
      id: event.id || index + 1,
      at: event.at || CLOCK_NOW,
      actorId: event.actorId ?? null,
      actorName: event.actorName || "Système",
      actorEmail: event.actorEmail || "",
      actorRole: event.actorRole || "system",
      type: event.type,
      severity: event.severity || inferAuditSeverity(event.type),
      targetType: event.targetType || "-",
      targetId: event.targetId ?? "-",
      scope: event.scope || "-",
      detail: event.detail || ""
    };
  }
  const text = String(event);
  const parts = text.split(" - ");
  return {
    id: index + 1,
    at: parts.length > 1 ? parts[0].replace(" ", "T") : CLOCK_NOW,
    actorId: null,
    actorName: "Système",
    actorEmail: "",
    actorRole: "system",
    type: "legacy",
    severity: "info",
    targetType: "-",
    targetId: "-",
    scope: "-",
    detail: parts.length > 1 ? parts.slice(1).join(" - ") : text
  };
}

function isPrivileged(user = currentUser()) {
  return ["validator", "admin"].includes(user?.role);
}

function isRequestVisibleToUser(request, user = currentUser()) {
  if (!user) return false;
  if (isPrivileged(user)) return true;
  if (user.role === "student") return request.requesterId === user.id;
  if (user.role === "trainer") {
    const requester = byId(state.users, request.requesterId);
    const course = courseForRequest(request);
    return requester?.className === user.className || course?.className === user.className || request.requesterId === user.id;
  }
  return false;
}

function isVmVisibleToUser(vm, user = currentUser()) {
  if (!user) return false;
  if (isPrivileged(user)) return true;
  if (user.role === "student") return vm.ownerId === user.id;
  if (user.role === "trainer") {
    const owner = byId(state.users, vm.ownerId);
    const request = byId(state.requests, vm.requestId);
    const course = request ? courseForRequest(request) : null;
    return owner?.className === user.className || course?.className === user.className || vm.ownerId === user.id;
  }
  return false;
}

function isCourseVisibleToUser(course, user = currentUser()) {
  if (!user) return false;
  if (isPrivileged(user)) return true;
  if (user.role === "trainer") return course.className === user.className;
  if (user.role === "student") {
    const hasRequest = state.requests.some((request) => request.courseId === course.id && isRequestVisibleToUser(request, user));
    const hasVm = state.vms.some((vm) => {
      const request = byId(state.requests, vm.requestId);
      return request?.courseId === course.id && isVmVisibleToUser(vm, user);
    });
    return hasRequest || hasVm;
  }
  return false;
}

function nowDate() {
  return new Date(CLOCK_NOW);
}

function toDate(value) {
  if (!value) return null;
  return new Date(value.includes("T") ? value : `${value}T00:00:00`);
}

function addHours(date, hours) {
  return new Date(date.getTime() + hours * 3600000);
}

function formatIsoLocal(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function laterDate(...dates) {
  return new Date(Math.max(...dates.filter(Boolean).map((date) => date.getTime())));
}

function hoursBetween(start, end) {
  const startDate = toDate(start);
  const endDate = toDate(end);
  if (!startDate || !endDate) return 0;
  return Math.max(0, (endDate - startDate) / 3600000);
}

function hoursUntil(dateValue) {
  const endDate = toDate(dateValue);
  if (!endDate) return 0;
  return (endDate - nowDate()) / 3600000;
}

function computeTemplatePricing(template) {
  const { flavor } = template;
  const cpuRatio = flavor.cpu / PRICING_MODEL.referenceCpu;
  const ramRatio = flavor.ramGb / PRICING_MODEL.referenceRamGb;
  const diskRatio = flavor.diskGb / PRICING_MODEL.referenceDiskGb;
  const multiplier =
    cpuRatio * PRICING_MODEL.weights.cpu +
    ramRatio * PRICING_MODEL.weights.ram +
    diskRatio * PRICING_MODEL.weights.disk;
  const monthlyChf = PRICING_MODEL.referenceMonthlyChf * multiplier;
  return {
    monthlyChf,
    hourlyChf: monthlyChf / PRICING_MODEL.billingHoursPerMonth,
    multiplier,
    source: PRICING_MODEL.sourceLabel
  };
}

function formatCost(value) {
  return `${Number(value || 0).toFixed(2)} CHF`;
}

function formatHourlyCost(value) {
  return `${Number(value || 0).toFixed(4)} CHF/h`;
}

function formatDateTime(value) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function canTransition(current, next) {
  return VALID_TRANSITIONS[current]?.includes(next) ?? false;
}

function transitionEntity(entity, nextStatus, timestampField) {
  if (entity.status === nextStatus) return true;
  if (!canTransition(entity.status, nextStatus)) {
    addEvent("transition_denied", `Transition refusée: ${entity.status} -> ${nextStatus} pour #${entity.id}.`, {
      severity: "warning",
      targetType: "state-machine",
      targetId: entity.id
    });
    return false;
  }
  entity.status = nextStatus;
  if (timestampField) entity[timestampField] = CLOCK_NOW;
  return true;
}

function templateForRequest(request) {
  if (!request) return null;
  return byId(state.templates, request.templateId);
}

function courseForRequest(request) {
  return byId(state.courses, request.courseId);
}

function ownerForRequest(request) {
  return byId(state.users, request.requesterId);
}

function estimatedRequestCost(request) {
  const template = templateForRequest(request);
  if (!template) return 0;
  return request.quantity * hoursBetween(request.startDate, request.endDate) * template.hourlyCostChf;
}

function realVmCost(vm) {
  const request = byId(state.requests, vm.requestId);
  const template = templateForRequest(request);
  if (!template) return 0;
  const usageEnd = vm.destroyedAt || (["destroyed", "expired"].includes(vm.status) ? vm.endDate : CLOCK_NOW);
  return hoursBetween(vm.provisionedAt || vm.createdAt, usageEnd) * template.hourlyCostChf;
}

function remainingBudget(course, realCost, committedCost = 0) {
  return Math.max(0, course.budgetChf - realCost - committedCost);
}

function budgetPercent(course, realCost, committedCost = 0) {
  if (!course.budgetChf) return 0;
  return Math.min(100, Math.round(((realCost + committedCost) / course.budgetChf) * 100));
}

function dataControls() {
  const scopedRequests = query.requests();
  const scopedVms = query.vms();
  const invalidDates = scopedRequests.filter((request) => toDate(request.endDate) <= toDate(request.startDate)).length;
  const missingVmEndDate = scopedVms.filter((vm) => !vm.endDate && vm.status !== "destroyed").length;
  const missingCostTemplate = scopedRequests.filter((request) => !templateForRequest(request)).length;
  const pendingProvisioning = query.requests({ status: "approved" }).length;
  const expiredToDestroy = query.vms({ status: "expired" }).length;
  const totalReal = scopedVms.reduce((sum, vm) => sum + realVmCost(vm), 0);
  const totalCommitted = scopedRequests
    .filter((request) => ["pending", "approved"].includes(request.status))
    .reduce((sum, request) => sum + estimatedRequestCost(request), 0);
  const totalBudget = query.costByCourse().reduce((sum, item) => sum + item.course.budgetChf, 0);
  const budgetRatio = totalBudget > 0 ? (totalReal + totalCommitted) / totalBudget : 0;

  return [
    {
      label: "Modèle prix",
      value: "Infomaniak",
      detail: `Base ${formatCost(PRICING_MODEL.referenceMonthlyChf)}/mois pour ${PRICING_MODEL.referenceCpu} CPU, ${PRICING_MODEL.referenceRamGb} Go RAM, ${PRICING_MODEL.referenceDiskGb} Go disque.`,
      tone: "success"
    },
    {
      label: "Dates de fin",
      value: missingVmEndDate === 0 && invalidDates === 0 ? "OK" : `${missingVmEndDate + invalidDates} anomalie(s)`,
      detail: "Aucune VM active sans échéance.",
      tone: missingVmEndDate === 0 && invalidDates === 0 ? "success" : "danger"
    },
    {
      label: "Catalogue coûts",
      value: missingCostTemplate === 0 ? "OK" : `${missingCostTemplate} modèle manquant`,
      detail: "Chaque demande utilise un modèle avec coût/h.",
      tone: missingCostTemplate === 0 ? "success" : "danger"
    },
    {
      label: "Provisionnement",
      value: pendingProvisioning,
      detail: "Demande(s) approuvée(s) prête(s) à transmettre à Terraform.",
      tone: pendingProvisioning > 0 ? "warning" : "neutral"
    },
    {
      label: "Nettoyage",
      value: expiredToDestroy,
      detail: "VM expirée(s) à détruire pour stopper les coûts.",
      tone: expiredToDestroy > 0 ? "warning" : "success"
    },
    {
      label: "Budget consommé",
      value: `${budgetPercent({ budgetChf: totalBudget }, totalReal, totalCommitted)}%`,
      detail: `${formatCost(totalReal)} réels + ${formatCost(totalCommitted)} engagés sur ${formatCost(totalBudget)}.`,
      tone: budgetRatio > 0.8 ? "danger" : "success"
    }
  ];
}

function statusBadge(status) {
  const labels = {
    pending: "En attente",
    approved: "Approuvée",
    provisioning: "Provisionnement",
    active: "Active",
    expiring: "Expire bientôt",
    expired: "Expirée",
    destroyed: "Détruite",
    refused: "Refusée",
    error: "Erreur"
  };
  return `<span class="badge status-${status}">${labels[status] || status}</span>`;
}

function inferAuditSeverity(type) {
  if (["permission_denied", "navigation_error", "transition_denied", "request_refused"].includes(type)) return "warning";
  if (["vm_destroyed"].includes(type)) return "danger";
  if (["request_approved", "vm_provisioned", "request_created", "csv_exported", "login"].includes(type)) return "success";
  return "info";
}

function auditSeverityBadge(severity) {
  const labels = {
    info: "Info",
    success: "OK",
    warning: "Attention",
    danger: "Critique"
  };
  const statusClass = severity === "danger" ? "error" : severity === "warning" ? "expiring" : "active";
  return `<span class="badge status-${statusClass}">${labels[severity] || severity}</span>`;
}

function formatAuditTarget(event) {
  if (!event.targetType || event.targetType === "-") return "-";
  return `${event.targetType} #${event.targetId ?? "-"}`;
}

function addEvent(type, detail, metadata = {}) {
  const actor = currentUser();
  const eventType = detail ? type : "info";
  const eventDetail = detail || type;
  state.events.unshift({
    id: Math.max(...state.events.map((event) => Number(event.id) || 0), 0) + 1,
    at: CLOCK_NOW,
    actorId: actor?.id ?? null,
    actorName: actor?.fullName || "Système",
    actorEmail: actor?.email || "",
    actorRole: actor?.role || "system",
    severity: metadata.severity || inferAuditSeverity(eventType),
    type: eventType,
    targetType: metadata.targetType || "-",
    targetId: metadata.targetId ?? "-",
    scope: metadata.scope || actor?.className || (isPrivileged(actor) ? "global" : "-"),
    detail: eventDetail
  });
}

function refreshLifecycleStatuses() {
  state.vms.forEach((vm) => {
    if (["destroyed", "error"].includes(vm.status)) return;
    const left = hoursUntil(vm.endDate);
    if (left < 0 && canTransition(vm.status, "expired")) {
      vm.status = "expired";
    } else if (left <= EXPIRING_THRESHOLD_HOURS && ["active"].includes(vm.status)) {
      vm.status = "expiring";
    }
  });

  state.requests.forEach((request) => {
    const linkedVms = state.vms.filter((vm) => vm.requestId === request.id);
    if (linkedVms.some((vm) => vm.status === "destroyed")) request.status = "destroyed";
    else if (linkedVms.some((vm) => vm.status === "expired")) request.status = "expired";
    else if (linkedVms.some((vm) => vm.status === "expiring")) request.status = "expiring";
    else if (linkedVms.some((vm) => vm.status === "active")) request.status = "active";
  });
}

const query = {
  requests(filters = {}) {
    return state.requests.filter((request) => {
      if (!filters.ignoreScope && !isRequestVisibleToUser(request)) return false;
      if (filters.status && request.status !== filters.status) return false;
      if (filters.courseId && request.courseId !== Number(filters.courseId)) return false;
      if (filters.userId && request.requesterId !== Number(filters.userId)) return false;
      if (filters.from && toDate(request.createdAt) < toDate(filters.from)) return false;
      if (filters.to && toDate(request.createdAt) > toDate(filters.to)) return false;
      return true;
    });
  },
  vms(filters = {}) {
    return state.vms.filter((vm) => {
      const request = byId(state.requests, vm.requestId);
      if (!request) return false;
      if (!filters.ignoreScope && !isVmVisibleToUser(vm)) return false;
      if (filters.status && vm.status !== filters.status) return false;
      if (filters.courseId && request.courseId !== Number(filters.courseId)) return false;
      if (filters.userId && vm.ownerId !== Number(filters.userId)) return false;
      if (filters.from && toDate(vm.createdAt) < toDate(filters.from)) return false;
      if (filters.to && toDate(vm.createdAt) > toDate(filters.to)) return false;
      return true;
    });
  },
  alerts() {
    return query.vms()
      .map((vm) => {
        const owner = byId(state.users, vm.ownerId);
        const left = hoursUntil(vm.endDate);
        if (vm.status === "destroyed") return null;
      if (vm.status === "expired" || left < 0) return { vm, owner, label: "À détruire", tone: "red" };
        if (vm.status === "error") return { vm, owner, label: "Erreur technique", tone: "red" };
        if (left <= EXPIRING_THRESHOLD_HOURS) return { vm, owner, label: `Expire dans ${Math.max(0, Math.ceil(left))}h`, tone: "amber" };
        return null;
      })
      .filter(Boolean);
  },
  costByCourse() {
    return state.courses.filter((course) => isCourseVisibleToUser(course)).map((course) => {
      const requests = query.requests({ courseId: course.id });
      const vms = query.vms({ courseId: course.id });
      const estimated = requests
        .filter((request) => request.status !== "refused")
        .reduce((sum, request) => sum + estimatedRequestCost(request), 0);
      const committed = requests
        .filter((request) => ["pending", "approved"].includes(request.status))
        .reduce((sum, request) => sum + estimatedRequestCost(request), 0);
      const real = vms.reduce((sum, vm) => sum + realVmCost(vm), 0);
      return {
        course,
        requestCount: requests.length,
        estimated,
        committed,
        real,
        remaining: remainingBudget(course, real, committed),
        percent: budgetPercent(course, real, committed)
      };
    });
  },
  costByClass() {
    const map = new Map();
    query.costByCourse().forEach(({ course }) => {
      map.set(course.className, { className: course.className, estimated: 0, committed: 0, real: 0 });
    });
    query.costByCourse().forEach((item) => {
      const row = map.get(item.course.className);
      row.estimated += item.estimated;
      row.committed += item.committed;
      row.real += item.real;
    });
    return [...map.values()];
  },
  kpis() {
    const scopedVms = query.vms();
    const activeVms = scopedVms.filter((vm) => ["active", "expiring"].includes(vm.status)).length;
    const pending = query.requests({ status: "pending" }).length;
    const expired = query.vms({ status: "expired" }).length;
    const error = query.vms({ status: "error" }).length;
    const destroyed = query.vms({ status: "destroyed" }).length;
    const realCost = scopedVms.reduce((sum, vm) => sum + realVmCost(vm), 0);
    return [
      ["VM actives", activeVms, "success"],
      ["Demandes en attente", pending, "warning"],
      ["VM expirees", expired, "danger"],
      ["VM en erreur", error, "danger"],
      ["VM détruites", destroyed, "neutral"],
      ["Coût réel actuel", formatCost(realCost), "accent"]
    ];
  }
};

function isViewAllowed(viewName) {
  const user = currentUser();
  if (!user) return viewName === "login";
  return VIEW_ACCESS[viewName]?.includes(user.role) ?? false;
}

function setView(viewName) {
  if (!isViewAllowed(viewName)) {
    addEvent("permission_denied", `Accès refusé à la vue ${viewName}.`, {
      severity: "warning",
      targetType: "view",
      targetId: viewName
    });
    alert("Accès réservé pour votre rôle.");
    saveState();
    return;
  }
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  const targetView = document.querySelector(`#view-${viewName}`);
  if (!targetView) {
    addEvent("navigation_error", `Vue inconnue: ${viewName}.`, {
      severity: "warning",
      targetType: "view",
      targetId: viewName
    });
    alert("Vue inconnue.");
    saveState();
    return;
  }
  targetView.classList.add("active");
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
}

function roleBadgeClass(role) {
  return `role-${role || "guest"}`;
}

function initialsFor(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase();
}

function renderLoginView() {
  document.body.classList.remove("is-authenticated", "login-leaving");
  document.body.classList.add("is-logged-out");
  document.querySelector(".sidebar").hidden = true;
  document.querySelector(".topbar").hidden = true;
  document.querySelector(".ops-strip").hidden = true;
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelector("#view-login").classList.add("active");
  renderLoginUsers();
}

function renderAuthShell() {
  const user = currentUser();
  if (!user) {
    renderLoginView();
    return;
  }

  document.body.classList.add("is-authenticated");
  document.body.classList.remove("is-logged-out");
  document.querySelector(".sidebar").hidden = false;
  document.querySelector(".topbar").hidden = false;
  document.querySelector(".ops-strip").hidden = false;
  document.querySelector("#view-login").classList.remove("active");

  // Topbar
  document.querySelector("#currentUserInitials span").textContent = initialsFor(user.fullName);
  document.querySelector("#currentUserName").textContent = user.fullName;
  document.querySelector("#currentUserRole").textContent = user.email;
  const badge = document.querySelector("#currentUserBadge");
  badge.textContent = roleLabel(user.role);
  badge.className = `role-badge ${roleBadgeClass(user.role)}`;

  // Bloc sidebar utilisateur
  const sidebarInitials = document.querySelector("#sidebarUserInitials");
  const sidebarName = document.querySelector("#sidebarUserName");
  const sidebarEmail = document.querySelector("#sidebarUserEmail");
  const sidebarBadge = document.querySelector("#sidebarUserBadge");
  if (sidebarInitials) sidebarInitials.textContent = initialsFor(user.fullName);
  if (sidebarName) sidebarName.textContent = user.fullName;
  if (sidebarEmail) sidebarEmail.textContent = user.email;
  if (sidebarBadge) {
    sidebarBadge.textContent = roleLabel(user.role);
    sidebarBadge.className = `role-badge ${roleBadgeClass(user.role)}`;
  }

  document.querySelectorAll(".nav-item").forEach((button) => {
    const allowed = isViewAllowed(button.dataset.view);
    button.disabled = !allowed;
    button.classList.toggle("is-disabled", !allowed);
    button.hidden = !allowed;
    button.style.display = allowed ? "" : "none";
    button.title = allowed ? "" : "Accès réservé à certains rôles";
  });

  document.querySelector('[data-view="validation"]').textContent = isPrivileged(user) ? "Demandes à valider" : "Mes demandes";
  document.querySelector('[data-view="vms"]').textContent = isPrivileged(user) ? "Parc VM" : "Mes VM";
}

function setActionState(selector, allowed) {
  const element = document.querySelector(selector);
  if (!element) return;
  element.disabled = !allowed;
  element.classList.toggle("is-disabled", !allowed);
  element.title = allowed ? "" : "Accès réservé";
}

function renderPermissionStates() {
  setActionState("#exportRequestsButton", can("exportCsv"));
  setActionState("#exportVmsButton", can("exportCsv"));
  setActionState("#resetDataButton", can("resetData"));
  setActionState("#simulateProvisionButton", can("provisionVm"));
  setActionState("#destroyExpiredButton", can("destroyExpiredVms"));
}

function renderLoginUsers() {
  const select = document.querySelector("#mockLoginUser");
  const list = document.querySelector("#mockLoginUsers");

  if (AUTH_MODE_FRONT === "oidc") {
    select.innerHTML = "";
    list.innerHTML = "";
    list.hidden = true;
    return;
  }

  const dotClass = (role) => {
    if (role === "admin") return "lp-dot-admin";
    if (role === "validator") return "lp-dot-valid";
    if (role === "trainer") return "lp-dot-trainer";
    return "lp-dot-student";
  };

  const roleClass = (role) => {
    if (role === "admin") return "lp-role-admin";
    if (role === "validator") return "lp-role-valid";
    if (role === "trainer") return "lp-role-trainer";
    return "lp-role-student";
  };

  list.hidden = false;
  select.innerHTML = state.users
    .map((user) => `<option value="${user.id}">${user.fullName} - ${roleLabel(user.role)}</option>`)
    .join("");

  list.innerHTML = state.users
    .map((user) => `
      <button class="lp-user-card" type="button" data-login-user="${user.id}">
        <div class="lp-user-av">${initialsFor(user.fullName)}</div>
        <div class="lp-user-info">
          <div class="lp-user-name">${user.fullName}</div>
          <div class="lp-user-meta">
            <div class="lp-dot ${dotClass(user.role)}"></div>
            <span class="lp-user-role ${roleClass(user.role)}">${roleLabel(user.role)}</span>
          </div>
        </div>
        <span class="lp-user-arrow">→</span>
      </button>
    `)
    .join("");
}

async function startInstitutionalLogin() {
  if (DATA_MODE !== "api") {
    loginAsSelectedUser();
    return;
  }

  const button = document.querySelector("#mockMicrosoftLoginButton");
  button.disabled = true;
  button.textContent = "Connexion en cours...";
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      credentials: "include",
      redirect: "manual"
    });
    const payload = await response.clone().json().catch(() => null);

    if (payload?.data?.mode === "mock") {
      const user = await apiRequest(`/auth/mock-login/${API_DEV_LOGIN_USER_ID}`, { method: "POST" });
      state.currentUser = buildAuthUser(mapApiUser(user));
      await hydrateFromApi();
      renderAll();
      setView("dashboard");
      return;
    }

    window.location.href = `${API_BASE_URL}/auth/login`;
  } catch (error) {
    console.error(error);
    alert(`Connexion impossible: ${error.message}. Verifiez que le backend FastAPI tourne sur ${API_ORIGIN}.`);
  } finally {
    button.disabled = false;
    button.innerHTML = `
      <span class="ms-grid" aria-hidden="true">
        <span></span><span></span><span></span><span></span>
      </span>
      Se connecter avec Microsoft 365
    `;
  }
}

async function loginAsSelectedUser() {
  if (AUTH_MODE_FRONT === "oidc") {
    await startInstitutionalLogin();
    return;
  }
  const user = byId(state.users, document.querySelector("#mockLoginUser").value);
  if (!user) return;
  document.body.classList.add("login-leaving");
  window.setTimeout(() => {
    user.lastLoginAt = CLOCK_NOW;
    state.currentUser = buildAuthUser(user);
    addEvent("login", `${user.fullName} connecté via Microsoft 365 simulé.`, {
      severity: "success",
      targetType: "user",
      targetId: user.id,
      scope: user.className || "global"
    });
    saveState();
    renderAll();
    document.body.classList.remove("login-leaving");
    setView("dashboard");
  }, 180);
}

async function logout() {
  const user = currentUser();
  addEvent("logout", `${user?.fullName || "Utilisateur"} déconnecté.`, {
    severity: "info",
    targetType: "user",
    targetId: user?.id || "-"
  });
  if (DATA_MODE === "api") {
    await apiRequest("/auth/logout", { method: "POST" }).catch((error) => console.warn(error));
  }
  localStorage.removeItem(AUTH_TOKEN_KEY);
  state.currentUser = null;
  saveState();
  renderAll();
}

function ratioPercent(value, total) {
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((value / total) * 100)));
}

function renderMiniBars(values, tone = "blue") {
  const max = Math.max(...values, 1);
  return values
    .map((value) => `<i class="mini-bar mini-bar-${tone}" style="height:${Math.max(12, Math.round((value / max) * 100))}%"></i>`)
    .join("");
}

function iconSvg(name) {
  const paths = {
    server: "M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4H4V6Zm0 8h16v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4Zm4-6h.01M8 16h.01",
    pulse: "M4 13h3l2-6 4 12 2-6h5",
    clock: "M12 6v6l4 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
    disk: "M4 7c0-2 16-2 16 0v10c0 2-16 2-16 0V7Zm0 0c0 2 16 2 16 0M4 12c0 2 16 2 16 0",
    check: "M20 6 9 17l-5-5",
    alert: "M12 9v4m0 4h.01M10.3 4.3 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z"
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${paths[name] || paths.server}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>`;
}

function renderDashboardCommandCenter() {
  const target = document.querySelector("#dashboardCommandCenter");
  if (!target) return;

  const scopedVms = query.vms();
  const scopedRequests = query.requests();
  const activeVms = scopedVms.filter((vm) => ["active", "expiring", "running"].includes(vm.status));
  const pendingRequests = scopedRequests.filter((request) => request.status === "pending");
  const expiredVms = scopedVms.filter((vm) => vm.status === "expired");
  const realCost = scopedVms.reduce((sum, vm) => sum + realVmCost(vm), 0);
  const totalDisk = scopedVms.reduce((sum, vm) => {
    const request = byId(state.requests, vm.requestId);
    const template = request ? templateForRequest(request) : null;
    return sum + Number(template?.flavor?.diskGb || 0);
  }, 0);
  const estimatedCapacity = Math.max(500, state.courses.length * 260);
  const storagePercent = ratioPercent(totalDisk, estimatedCapacity);
  const healthScore = scopedVms.length ? ratioPercent(activeVms.length, scopedVms.filter((vm) => vm.status !== "destroyed").length || 1) : 100;
  const costByClass = query.costByClass();
  const classCosts = ["E1", "E2", "E3", "E4", "E5"].map((className) => {
    const match = costByClass.find((row) => row.className === className);
    return { className, real: match?.real || 0, committed: match?.committed || 0, budget: 260 };
  });
  const statusRows = [
    ["Actives", activeVms.length, "success"],
    ["En attente", pendingRequests.length, "warning"],
    ["Expirees", expiredVms.length, "danger"],
    ["Erreur", scopedVms.filter((vm) => vm.status === "error").length, "danger"],
    ["Detruites", scopedVms.filter((vm) => vm.status === "destroyed").length, "neutral"]
  ];
  const activity = state.events.slice(0, 5);
  const topStudents = state.users
    .filter((user) => ["student", "trainer"].includes(user.role))
    .map((user) => ({
      user,
      vms: scopedVms.filter((vm) => vm.ownerId === user.id).length,
      cost: scopedVms.filter((vm) => vm.ownerId === user.id).reduce((sum, vm) => sum + realVmCost(vm), 0)
    }))
    .sort((a, b) => b.vms - a.vms || b.cost - a.cost)
    .slice(0, 5);
  const recentVms = scopedVms
    .slice()
    .sort((a, b) => toDate(b.createdAt || b.provisionedAt || b.endDate) - toDate(a.createdAt || a.provisionedAt || a.endDate))
    .slice(0, 6);
  const vmTimelineValues = [2, 4, 3, activeVms.length + 1, activeVms.length, scopedVms.length, Math.max(activeVms.length, scopedVms.length - expiredVms.length)];

  target.innerHTML = `
    <section class="command-hero">
      <div class="command-hero-copy">
        <span class="eyebrow">Cloud operations center</span>
        <h3>Supervision temps reel des environnements pedagogiques</h3>
        <p>Vue consolidee des VM, demandes, couts et fins de vie. Le dashboard reste pret a brancher sur Prometheus/Grafana ou les endpoints FastAPI.</p>
        <div class="dashboard-filters" aria-label="Filtres dashboard">
          <button class="filter-pill is-active" type="button">Toutes classes</button>
          <button class="filter-pill" type="button">E1</button>
          <button class="filter-pill" type="button">E2</button>
          <button class="filter-pill" type="button">E3</button>
          <button class="filter-pill" type="button">E4</button>
          <button class="filter-pill" type="button">E5</button>
        </div>
      </div>
      <div class="command-health-card">
        <span>Disponibilite pilote</span>
        <strong>${healthScore}%</strong>
        <div class="ring-meter" style="--value:${healthScore}"><b>${activeVms.length}</b><small>VM actives</small></div>
      </div>
      <div class="command-cost-card">
        <span>Cout reel courant</span>
        <strong>${formatCost(realCost)}</strong>
        <p>${pendingRequests.length} demande(s) en attente - ${expiredVms.length} VM a nettoyer</p>
      </div>
    </section>

    <section class="metrics-command-grid">
      ${[
        ["Total VM", scopedVms.length, "+12% vs semaine", "server", "blue"],
        ["VM actives", activeVms.length, `${ratioPercent(activeVms.length, scopedVms.length)}% du parc`, "pulse", "green"],
        ["Demandes", pendingRequests.length, "validation requise", "clock", "amber"],
        ["Stockage", `${totalDisk} Go`, `${storagePercent}% utilise`, "disk", "blue"],
        ["Uptime", "99.9%", "aucun incident critique", "check", "green"],
        ["Alertes", query.alerts().length, "expiration / erreur", "alert", "red"]
      ].map(([label, value, detail, icon, tone], index) => `
        <article class="metric-command-card metric-${tone}">
          <div class="metric-icon metric-icon-${tone}" aria-hidden="true">${iconSvg(icon)}</div>
          <span>${label}</span>
          <strong>${value}</strong>
          <small>${detail}</small>
          <div class="mini-chart">${renderMiniBars(vmTimelineValues.map((v) => Math.max(1, v + index)), tone)}</div>
        </article>
      `).join("")}
    </section>

    <section class="dashboard-charts-grid">
      <article class="chart-panel chart-wide">
        <div class="chart-head">
          <div><span class="eyebrow">30 derniers jours</span><h3>Creation et fin de vie des VM</h3></div>
          <div class="range-tabs"><button class="is-active" type="button">30j</button><button type="button">90j</button><button type="button">Tout</button></div>
        </div>
        <div class="line-chart" aria-label="Evolution des VM">
          ${vmTimelineValues.map((value, index) => `<i style="--x:${index};--h:${Math.max(16, value * 14)}px"></i>`).join("")}
        </div>
        <div class="chart-legend"><span class="dot green"></span>Actives <span class="dot blue"></span>Creees <span class="dot red"></span>Expirees</div>
      </article>

      <article class="chart-panel">
        <div class="chart-head"><div><span class="eyebrow">Ressources</span><h3>Allocation actuelle</h3></div></div>
        <div class="resource-donut" style="--cpu:${Math.min(92, activeVms.length * 9)};--ram:${Math.min(88, activeVms.length * 11)};--disk:${storagePercent}">
          <strong>${storagePercent}%</strong><span>stockage</span>
        </div>
        <div class="resource-list">
          <span><b class="dot blue"></b>CPU ${Math.min(92, activeVms.length * 9)}%</span>
          <span><b class="dot green"></b>RAM ${Math.min(88, activeVms.length * 11)}%</span>
          <span><b class="dot amber"></b>Disque ${storagePercent}%</span>
        </div>
      </article>

      <article class="chart-panel">
        <div class="chart-head"><div><span class="eyebrow">Budget</span><h3>Cout mensuel par classe</h3></div></div>
        <div class="class-bars">
          ${classCosts.map((row) => `
            <div>
              <span>${row.className}</span>
              <i><b style="width:${ratioPercent(row.real + row.committed, row.budget)}%"></b></i>
              <strong>${formatCost(row.real + row.committed)}</strong>
            </div>
          `).join("")}
        </div>
      </article>

      <article class="chart-panel">
        <div class="chart-head"><div><span class="eyebrow">Cycle</span><h3>Statuts du parc</h3></div></div>
        <div class="status-bars">
          ${statusRows.map(([label, count, tone]) => `
            <div>
              <span>${label}</span>
              <i><b class="bar-${tone}" style="width:${ratioPercent(count, Math.max(1, scopedVms.length, pendingRequests.length))}%"></b></i>
              <strong>${count}</strong>
            </div>
          `).join("")}
        </div>
      </article>
    </section>

    <section class="dashboard-bottom-grid">
      <article class="panel recent-vms-panel">
        <div class="chart-head"><div><span class="eyebrow">Parc recent</span><h3>Recent Virtual Machines</h3></div><span class="live-dot">Live</span></div>
        <div class="mini-table">
          ${recentVms.length ? recentVms.map((vm) => {
            const owner = byId(state.users, vm.ownerId);
            return `
              <div class="mini-table-row">
                <div><strong>${vm.name}</strong><span>${vm.ip || "IP en attente"}</span></div>
                <div class="owner-pill"><b>${initialsFor(owner?.fullName || "VM")}</b><span>${owner?.fullName || "Inconnu"}<small>${owner?.className || "GIT"}</small></span></div>
                ${statusBadge(vm.status)}
                <strong class="num">${formatCost(realVmCost(vm))}</strong>
              </div>
            `;
          }).join("") : `<p>Aucune VM visible pour ce profil.</p>`}
        </div>
      </article>

      <aside class="dashboard-widgets">
        <article class="panel widget-panel">
          <div class="chart-head"><div><span class="eyebrow">Activite</span><h3>Recent Activity</h3></div></div>
          <div class="activity-feed">
            ${activity.map((event) => `<div><b></b><span>${event.detail}</span><small>${formatDateTime(event.at)}</small></div>`).join("") || "<p>Aucune activite recente.</p>"}
          </div>
        </article>
        <article class="panel widget-panel">
          <div class="chart-head"><div><span class="eyebrow">Consommation</span><h3>Top VM Consumers</h3></div></div>
          <div class="top-students">
            ${topStudents.map(({ user, vms, cost }) => `
              <div><b>${initialsFor(user.fullName)}</b><span>${user.fullName}<small>${user.className || roleLabel(user.role)}</small></span><strong>${vms} VM</strong><i style="width:${ratioPercent(cost, 5)}%"></i></div>
            `).join("") || "<p>Aucun utilisateur visible.</p>"}
          </div>
        </article>
      </aside>
    </section>
  `;
}

function renderKpis() {
  document.querySelector("#kpiGrid").innerHTML = query.kpis()
    .map(([label, value, tone]) => {
      const featuredClass = label === "Coût réel actuel" ? " kpi-featured" : "";
      return `<div class="kpi kpi-${tone}${featuredClass}"><span>${label}</span><strong>${value}</strong></div>`;
    })
    .join("");
}

function renderCatalog() {
  const icon = (path) => `
    <svg class="spec-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="${path}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
    </svg>
  `;
  document.querySelector("#templateGrid").innerHTML = state.templates
    .map((template) => {
      const course = byId(state.courses, template.courseId);
      return `
        <article class="template-card">
          <div class="course-mark" aria-hidden="true">${String(course.name).slice(0, 2).toUpperCase()}</div>
          <div class="template-content">
            <div class="template-card-head">
              <div>
                <span class="template-course">${course.className}</span>
                <h3>${course.name}</h3>
              </div>
              <span class="template-price">${formatHourlyCost(template.hourlyCostChf)}</span>
            </div>
            <p>${template.description}</p>
            <div class="template-meta">
              <span>${icon("M4 7h16M4 12h16M4 17h16")} ${template.flavor.cpu} CPU</span>
              <span>${icon("M6 19V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2Z")} ${template.flavor.ramGb} Go RAM</span>
              <span>${icon("M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4m18 0-3.5-7h-11L3 15m18 0H3")} ${template.flavor.diskGb} Go disque</span>
              <span>${template.flavor.name}</span>
            </div>
            <div class="template-tools">
              <strong>Outils inclus</strong>
              <span>${template.tools.slice(0, 5).join(", ")}</span>
            </div>
            <div class="template-foot">
              <span>${template.image}</span>
              <span>${formatCost(template.monthlyCostChf)}/mois estimé</span>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderSelectors() {
  const user = currentUser();
  const requesterSelect = document.querySelector("#requesterId");
  const requesterOptions = can("createForOtherUser", user)
    ? state.users.filter((item) => ["student", "trainer"].includes(item.role))
    : state.users.filter((item) => item.id === user?.id);
  requesterSelect.innerHTML = requesterOptions
    .map((item) => `<option value="${item.id}">${item.fullName} - ${roleLabel(item.role)}</option>`)
    .join("");
  requesterSelect.value = can("createForOtherUser", user) ? requesterSelect.value || requesterOptions[0]?.id : user?.id || "";
  requesterSelect.disabled = !can("createForOtherUser", user);

  const templateSelect = document.querySelector("#templateId");
  templateSelect.innerHTML = state.templates
    .map((template) => {
      const course = byId(state.courses, template.courseId);
      return `<option value="${template.id}">${template.name} - ${course.name}</option>`;
    })
    .join("");

  document.querySelector("#startDate").value ||= "2026-06-17";
  document.querySelector("#endDate").value ||= "2026-06-24";
  const quantityInput = document.querySelector("#quantity");
  const maxQuantity = can("createGroupRequest", user) ? 20 : 1;
  quantityInput.max = maxQuantity;
  if (Number(quantityInput.value || 1) > maxQuantity) quantityInput.value = maxQuantity;
  if (!can("createGroupRequest", user)) quantityInput.value = 1;
}

function renderRequests() {
  document.querySelector("#requestsTable").innerHTML = query.requests()
    .map((request) => {
      const user = ownerForRequest(request);
      const course = courseForRequest(request);
      const template = templateForRequest(request);
      const actions = [];
      if (request.status === "pending" && can("approveRequest")) {
        actions.push(`<button class="action-button approve" data-approve="${request.id}">Approuver</button>`);
      }
      if (request.status === "pending" && can("refuseRequest")) {
        actions.push(`<button class="action-button refuse" data-refuse="${request.id}">Refuser</button>`);
      }
      if (request.status === "approved" && can("provisionVm")) {
        actions.push(`<button class="action-button approve" data-provision="${request.id}">Provisionner</button>`);
      }
      return `
        <tr>
          <td>#${request.id}</td>
          <td>${user.fullName}</td>
          <td>${course.name}</td>
          <td>${template.name}</td>
          <td class="num">${request.quantity}</td>
          <td>${request.startDate} -> ${request.endDate}</td>
          <td class="num">${formatCost(estimatedRequestCost(request))}</td>
          <td>${statusBadge(request.status)}</td>
          <td>${actions.length ? actions.join("") : "-"}</td>
        </tr>
      `;
    })
    .join("");
}

function renderVms() {
  document.querySelector("#vmsTable").innerHTML = query.vms()
    .map((vm) => {
      const owner = byId(state.users, vm.ownerId);
      const request = byId(state.requests, vm.requestId);
      const template = templateForRequest(request);
      return `
        <tr>
          <td>${vm.name}</td>
          <td>${owner.fullName}</td>
          <td>${vm.ip}</td>
          <td>${statusBadge(vm.status)}</td>
          <td>${vm.network}</td>
          <td>${vm.endDate}</td>
          <td class="num">${formatCost(realVmCost(vm))}</td>
          <td class="num">${formatHourlyCost(template.hourlyCostChf)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderAlerts() {
  const alerts = query.alerts();
  document.querySelector("#alertsList").innerHTML =
    alerts.length === 0
      ? `<p>Aucune alerte.</p>`
      : alerts
          .map(({ vm, owner, label, tone }) => `
            <div class="list-item">
              <div>
                <strong>${vm.name}</strong>
                <span>${owner.fullName} - fin ${vm.endDate} - coût réel ${formatCost(realVmCost(vm))}</span>
              </div>
              <span class="badge status-${tone === "red" ? "error" : "expiring"}">${label}</span>
            </div>
          `)
          .join("");
}

function renderCourseCosts() {
  const rows = query.costByCourse();
  document.querySelector("#courseCosts").innerHTML = rows.length === 0
    ? `<p>Aucun budget visible pour ce profil.</p>`
    : rows
    .map(({ course, requestCount, committed, real, remaining, percent }) => `
      <div class="list-item cost-row">
        <div>
          <strong>${course.name}</strong>
          <span>${course.className} - ${requestCount} demande(s) - estimé en attente ${formatCost(committed)} - engagé réel ${formatCost(real)} - reste ${formatCost(remaining)}</span>
          <div class="meter" aria-label="Budget consommé ${percent}%">
            <i style="width: ${percent}%"></i>
          </div>
        </div>
        <span class="badge status-active">${formatCost(real)}</span>
      </div>
    `)
    .join("");
}

function renderDataControls() {
  document.querySelector("#dataControlsList").innerHTML = dataControls()
    .map((control) => `
      <div class="proof-card proof-${control.tone}">
        <span>${control.label}</span>
        <strong>${control.value}</strong>
        <small>${control.detail}</small>
      </div>
    `)
    .join("");
}

function renderLifecycle() {
  const steps = [
    ["Demandes", state.requests.length],
    ["En attente", query.requests({ status: "pending" }).length],
    ["Approuvées", query.requests({ status: "approved" }).length],
    ["Provisionnement", query.requests({ status: "provisioning" }).length],
    ["Actives", query.vms().filter((vm) => ["active", "expiring"].includes(vm.status)).length],
    ["Expirées", query.vms({ status: "expired" }).length],
    ["Détruites", query.vms({ status: "destroyed" }).length]
  ];
  document.querySelector("#lifecycleList").innerHTML = steps
    .map(([label, count]) => `
      <div class="list-item">
        <div>
          <strong>${label}</strong>
          <span>Étape du cycle de vie</span>
        </div>
        <span class="badge">${count}</span>
      </div>
    `)
    .join("");
}

function renderEvents() {
  document.querySelector("#eventsList").innerHTML = state.events
    .slice(0, 7)
    .map((event) => `
      <div class="list-item compact">
        <div>
          <strong>${event.type} - ${formatAuditTarget(event)}</strong>
          <span>${formatDateTime(event.at)} - ${event.actorName} (${roleLabel(event.actorRole)}) - ${event.detail}</span>
        </div>
        ${auditSeverityBadge(event.severity)}
      </div>
    `)
    .join("");
}

function renderAuditFilters() {
  const typeSelect = document.querySelector("#auditTypeFilter");
  const severitySelect = document.querySelector("#auditSeverityFilter");
  const actorSelect = document.querySelector("#auditActorFilter");
  const types = [...new Set(state.events.map((event) => event.type))].sort();
  const severities = [...new Set(state.events.map((event) => event.severity))].sort();
  const actors = [...new Set(state.events.map((event) => event.actorName))].sort();
  const currentType = typeSelect.value;
  const currentSeverity = severitySelect.value;
  const currentActor = actorSelect.value;
  typeSelect.innerHTML = `<option value="">Tous les types</option>${types.map((type) => `<option value="${type}">${type}</option>`).join("")}`;
  severitySelect.innerHTML = `<option value="">Toutes gravités</option>${severities.map((severity) => `<option value="${severity}">${severity}</option>`).join("")}`;
  actorSelect.innerHTML = `<option value="">Tous les acteurs</option>${actors.map((actor) => `<option value="${actor}">${actor}</option>`).join("")}`;
  typeSelect.value = currentType;
  severitySelect.value = currentSeverity;
  actorSelect.value = currentActor;
}

function renderAudit() {
  const table = document.querySelector("#auditTable");
  if (!table) return;
  if (!can("viewAudit")) {
    table.innerHTML = `<tr><td colspan="7">Accès réservé aux validateurs et admins.</td></tr>`;
    return;
  }
  renderAuditFilters();
  const typeFilter = document.querySelector("#auditTypeFilter").value;
  const severityFilter = document.querySelector("#auditSeverityFilter").value;
  const actorFilter = document.querySelector("#auditActorFilter").value;
  table.innerHTML = state.events
    .filter((event) => !typeFilter || event.type === typeFilter)
    .filter((event) => !severityFilter || event.severity === severityFilter)
    .filter((event) => !actorFilter || event.actorName === actorFilter)
    .sort((a, b) => toDate(b.at) - toDate(a.at))
    .map((event) => `
      <tr>
        <td>${formatDateTime(event.at)}</td>
        <td>${event.actorName}<br><small>${event.actorEmail || "-"}</small></td>
        <td>${roleLabel(event.actorRole)}</td>
        <td>${auditSeverityBadge(event.severity)}</td>
        <td>${event.type}</td>
        <td>${formatAuditTarget(event)}</td>
        <td>${event.detail}</td>
      </tr>
    `)
    .join("");
}

function updateEstimate() {
  const template = byId(state.templates, document.querySelector("#templateId").value);
  const quantity = Number(document.querySelector("#quantity").value || 1);
  const startDate = document.querySelector("#startDate").value;
  const endDate = document.querySelector("#endDate").value;
  if (!template || !startDate || !endDate) return;
  const cost = quantity * hoursBetween(startDate, endDate) * template.hourlyCostChf;
  document.querySelector("#requestEstimate").textContent = `Coût estimé : ${formatCost(cost)}`;
}

async function createRequest(event) {
  event.preventDefault();
  const user = currentUser();
  if (!user) {
    alert("Vous devez être connecté.");
    return;
  }
  const template = byId(state.templates, document.querySelector("#templateId").value);
  const startDate = document.querySelector("#startDate").value;
  const endDate = document.querySelector("#endDate").value;
  const quantity = Number(document.querySelector("#quantity").value);
  const maxQuantity = can("createGroupRequest", user) ? 20 : 1;
  if (quantity > maxQuantity) {
    alert("Action non autorisée pour votre rôle.");
    addEvent("permission_denied", `Quantité ${quantity} refusée pour le rôle ${user.role}.`, {
      severity: "warning",
      targetType: "request-quantity",
      targetId: quantity
    });
    saveState();
    renderAudit();
    return;
  }
  if (quantity > 1 && !requirePermission("createGroupRequest")) return;
  if (new Date(endDate) <= new Date(startDate)) {
    alert("La date de fin doit être après la date de début.");
    return;
  }
  if (DATA_MODE === "api") {
    try {
      await apiRequest("/vm-requests", {
        method: "POST",
        body: JSON.stringify({
          requester_id: can("createForOtherUser", user) ? Number(document.querySelector("#requesterId").value) : user.id,
          course_id: template.courseId,
          template_id: template.id,
          quantity,
          start_date: startDate,
          end_date: endDate,
          request_reason: document.querySelector("#requestReason").value
        })
      });
      await refreshFromApiAndRender();
      setView("validation");
      event.target.reset();
      renderSelectors();
      updateEstimate();
    } catch (error) {
      alert(`Demande non enregistree: ${error.message}`);
    }
    return;
  }
  const request = {
    id: Math.max(...state.requests.map((item) => item.id), 0) + 1,
    requesterId: can("createForOtherUser", user) ? Number(document.querySelector("#requesterId").value) : user.id,
    courseId: template.courseId,
    templateId: template.id,
    quantity,
    startDate,
    endDate,
    status: "pending",
    reason: document.querySelector("#requestReason").value,
    validatorId: null,
    decisionComment: "",
    createdAt: CLOCK_NOW,
    approvedAt: null,
    provisioningAt: null,
    provisionedAt: null,
    destroyedAt: null
  };
  state.requests.push(request);
  addEvent("request_created", `Nouvelle demande #${request.id} enregistrée pour validation.`, {
    severity: "success",
    targetType: "request",
    targetId: request.id,
    scope: ownerForRequest(request)?.className || courseForRequest(request)?.className || "-"
  });
  saveState();
  renderAll();
  setView("validation");
  event.target.reset();
  renderSelectors();
  updateEstimate();
}

async function approveRequest(id) {
  if (!requirePermission("approveRequest")) return;
  const request = byId(state.requests, id);
  if (DATA_MODE === "api") {
    try {
      await apiRequest(`/vm-requests/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: "approved",
          validator_id: currentUser().id,
          decision_comment: "Demande approuvee."
        })
      });
      await refreshFromApiAndRender();
    } catch (error) {
      alert(`Validation impossible: ${error.message}`);
    }
    return;
  }
  if (!transitionEntity(request, "approved", "approvedAt")) return;
  request.validatorId = currentUser().id;
  request.decisionComment = "Demande approuvée.";
  addEvent("request_approved", `Demande #${request.id} approuvée. Provisionnement prêt à démarrer.`, {
    severity: "success",
    targetType: "request",
    targetId: request.id,
    scope: ownerForRequest(request)?.className || courseForRequest(request)?.className || "-"
  });
  saveState();
  renderAll();
}

async function refuseRequest(id) {
  if (!requirePermission("refuseRequest")) return;
  const request = byId(state.requests, id);
  if (DATA_MODE === "api") {
    try {
      await apiRequest(`/vm-requests/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: "refused",
          validator_id: currentUser().id,
          decision_comment: "Demande refusee."
        })
      });
      await refreshFromApiAndRender();
    } catch (error) {
      alert(`Refus impossible: ${error.message}`);
    }
    return;
  }
  if (!transitionEntity(request, "refused", null)) return;
  request.validatorId = currentUser().id;
  request.decisionComment = "Demande refusée.";
  addEvent("request_refused", `Demande #${request.id} refusée.`, {
    severity: "warning",
    targetType: "request",
    targetId: request.id,
    scope: ownerForRequest(request)?.className || courseForRequest(request)?.className || "-"
  });
  saveState();
  renderAll();
}

async function provisionRequest(requestId) {
  if (!requirePermission("provisionVm")) return;
  const request = requestId ? byId(state.requests, requestId) : state.requests.find((item) => item.status === "approved");
  if (!request) {
    alert("Aucune demande approuvée à provisionner.");
    return;
  }
  if (request.status !== "approved") {
    alert(`La demande #${request.id} n'est pas en statut approuvé.`);
    return;
  }
  if (DATA_MODE === "api") {
    try {
      await apiRequest(`/vm-requests/${request.id}/provision`, { method: "POST" });
      await refreshFromApiAndRender();
      alert("Intention de provisioning envoyee. Terraform pourra confirmer le resultat via l'API.");
    } catch (error) {
      alert(`Provisioning impossible: ${error.message}`);
    }
    return;
  }
  const owner = ownerForRequest(request);
  const template = templateForRequest(request);
  const course = courseForRequest(request);
  if (!transitionEntity(request, "provisioning", "provisioningAt")) return;
  const firstVmId = Math.max(...state.vms.map((item) => item.id), 0) + 1;
  const slug = owner.fullName.toLowerCase().split(" ")[0];
  const network = owner.className ? `class-${owner.className.toLowerCase()}` : `class-course-${request.courseId}`;
  const requestedQuantity = Number(request.quantity || 1);
  const targetQuantity = Math.min(requestedQuantity, 50);
  if (requestedQuantity > 50) {
    console.warn(`Demande #${request.id}: ${requestedQuantity} VM demandées, simulation limitée à 50 VM.`);
  }
  const now = nowDate();
  const startFloor = toDate(request.startDate);
  const demoProvisionedAt = laterDate(startFloor, addHours(now, -4));
  const demoCreatedAt = laterDate(startFloor, addHours(demoProvisionedAt, -0.1));
  const createdVms = [];

  for (let index = 0; index < targetQuantity; index += 1) {
    const vmId = firstVmId + index;
    const vm = {
      id: vmId,
      requestId: request.id,
      ownerId: owner.id,
      providerVmId: `pilot-vm-${1000 + vmId}`,
      name: `git-${template.slug}-${slug}-${String(index + 1).padStart(3, "0")}`,
      ip: `10.10.${request.courseId}.${20 + vmId}`,
      status: "provisioning",
      sshUser: "student",
      sshKey: `SHA256:lab-${slug}`,
      network,
      // Décalage volontaire pour éviter un coût réel à 0 CHF sur une VM tout juste provisionnée, plus réaliste en démo.
      createdAt: formatIsoLocal(demoCreatedAt),
      provisionedAt: null,
      startDate: request.startDate,
      endDate: request.endDate,
      destroyedAt: null
    };
    state.vms.push(vm);
    transitionEntity(vm, "active", null);
    vm.provisionedAt = formatIsoLocal(demoProvisionedAt);
    createdVms.push(vm);
  }

  transitionEntity(request, "active", null);
  request.provisionedAt = formatIsoLocal(demoProvisionedAt);
  refreshLifecycleStatuses();
  const cappedMessage = requestedQuantity > targetQuantity ? ` Demande limitée à ${targetQuantity}/${requestedQuantity} pour la démo.` : "";
  addEvent("vm_provisioned", `${createdVms.length}/${targetQuantity} VM provisionnée(s) pour la demande #${request.id} (${template.name}, ${owner.className || course.className}).${cappedMessage}`, {
    severity: "success",
    targetType: "request",
    targetId: request.id,
    scope: owner.className || course.className
  });
  saveState();
  renderAll();
}

function simulateProvisioning() {
  provisionRequest();
}

async function destroyExpiredVms() {
  if (!requirePermission("destroyExpiredVms")) return;
  const expired = state.vms.filter((vm) => vm.status === "expired");
  if (expired.length === 0) {
    alert("Aucune VM expirée à détruire.");
    return;
  }
  if (DATA_MODE === "api") {
    try {
      await Promise.all(expired.map((vm) => apiRequest(`/virtual-machines/${vm.id}/destruction-result`, {
        method: "PATCH",
        body: JSON.stringify({
          status: "destroyed",
          destroyed_at: new Date().toISOString()
        })
      })));
      await refreshFromApiAndRender();
    } catch (error) {
      alert(`Destruction non confirmee: ${error.message}`);
    }
    return;
  }
  expired.forEach((vm) => {
    transitionEntity(vm, "destroyed", "destroyedAt");
    const request = byId(state.requests, vm.requestId);
    if (request && canTransition(request.status, "destroyed")) transitionEntity(request, "destroyed", "destroyedAt");
    addEvent("vm_destroyed", `VM ${vm.name} détruite après expiration. Coût réel: ${formatCost(realVmCost(vm))}.`, {
      severity: "danger",
      targetType: "vm",
      targetId: vm.id,
      scope: byId(state.users, vm.ownerId)?.className || "-"
    });
  });
  saveState();
  renderAll();
}

function toCsv(rows) {
  if (rows.length === 0) return "";
  const separator = ";";
  const headers = Object.keys(rows[0]);
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  return "\uFEFF" + [headers.join(separator), ...rows.map((row) => headers.map((h) => escape(row[h])).join(separator))].join("\n");
}

function downloadCsv(filename, csv) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportRequests() {
  if (!requirePermission("exportCsv")) return;
  const rows = query.requests().map((request) => {
    const user = ownerForRequest(request);
    const course = courseForRequest(request);
    const template = templateForRequest(request);
    return {
      id: request.id,
      demandeur: user.fullName,
      role: user.role,
      classe: user.className || course.className,
      cours: course.name,
      template: template.slug,
      flavor: template.flavor.name,
      cpu: template.flavor.cpu,
      ram_gb: template.flavor.ramGb,
      disk_gb: template.flavor.diskGb,
      quantite: request.quantity,
      statut: request.status,
      created_at: formatDateTime(request.createdAt),
      approved_at: formatDateTime(request.approvedAt),
      provisioned_at: formatDateTime(request.provisionedAt),
      end_date: request.endDate,
      cout_estime_chf: estimatedRequestCost(request).toFixed(2),
      cout_horaire_chf: template.hourlyCostChf.toFixed(4),
      prix_source: PRICING_MODEL.sourceLabel
    };
  });
  downloadCsv("demandes-vm.csv", toCsv(rows));
  addEvent("csv_exported", "Export CSV des demandes genere.", {
    severity: "success",
    targetType: "export",
    targetId: "requests"
  });
  saveState();
  renderAll();
}

function exportVms() {
  if (!requirePermission("exportCsv")) return;
  const rows = query.vms().map((vm) => {
    const owner = byId(state.users, vm.ownerId);
    const request = byId(state.requests, vm.requestId);
    const course = courseForRequest(request);
    const template = templateForRequest(request);
    return {
      id: vm.id,
      nom: vm.name,
      proprietaire: owner.fullName,
      classe: owner.className || course.className,
      cours: course.name,
      template: template.slug,
      provider_vm_id: vm.providerVmId,
      ip: vm.ip,
      statut: vm.status,
      reseau: vm.network,
      provisioned_at: formatDateTime(vm.provisionedAt),
      end_date: vm.endDate,
      destroyed_at: formatDateTime(vm.destroyedAt),
      cout_reel_chf: realVmCost(vm).toFixed(2),
      cout_horaire_chf: template.hourlyCostChf.toFixed(4),
      prix_source: PRICING_MODEL.sourceLabel
    };
  });
  downloadCsv("machines-virtuelles.csv", toCsv(rows));
  addEvent("csv_exported", "Export CSV des VM genere.", {
    severity: "success",
    targetType: "export",
    targetId: "vms"
  });
  saveState();
  renderAll();
}

function renderAll() {
  if (!currentUser()) {
    renderLoginView();
    return;
  }

  refreshLifecycleStatuses();
  renderAuthShell();
  renderDashboardCommandCenter();
  renderKpis();
  renderCatalog();
  renderSelectors();
  renderRequests();
  renderVms();
  renderAlerts();
  renderCourseCosts();
  renderLifecycle();
  renderEvents();
  renderAudit();
  renderDataControls();
  renderPermissionStates();
}

async function initApp() {
  if (DATA_MODE !== "api") {
    renderAll();
    updateEstimate();
    return;
  }

  try {
    const user = await apiRequest("/auth/me");
    state.currentUser = buildAuthUser(mapApiUser(user));
    await hydrateFromApi();
    renderAll();
    updateEstimate();
  } catch {
    state.currentUser = null;
    renderAll();
  }
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.querySelector("#requestForm").addEventListener("submit", createRequest);
document.querySelector("#templateId").addEventListener("change", updateEstimate);
document.querySelector("#quantity").addEventListener("input", updateEstimate);
document.querySelector("#startDate").addEventListener("change", updateEstimate);
document.querySelector("#endDate").addEventListener("change", updateEstimate);
document.querySelector("#simulateProvisionButton").addEventListener("click", simulateProvisioning);
document.querySelector("#destroyExpiredButton").addEventListener("click", destroyExpiredVms);
document.querySelector("#exportRequestsButton").addEventListener("click", exportRequests);
document.querySelector("#exportVmsButton").addEventListener("click", exportVms);
document.querySelector("#resetDataButton").addEventListener("click", () => {
  if (!requirePermission("resetData")) return;
  localStorage.removeItem(STORAGE_KEY);
  state = structuredClone(seed);
  state = normaliseState(state);
  renderAll();
});
document.querySelector("#credentialLoginForm").addEventListener("submit", credentialLogin);
document.querySelector("#mockMicrosoftLoginButton").addEventListener("click", loginAsSelectedUser);
document.querySelector("#mockLoginUsers").addEventListener("click", (event) => {
  const card = event.target.closest("[data-login-user]");
  if (!card) return;
  document.querySelector("#mockLoginUser").value = card.dataset.loginUser;
  loginAsSelectedUser();
});
document.querySelector("#logoutButton").addEventListener("click", logout);
document.querySelector("#auditTypeFilter").addEventListener("change", renderAudit);
document.querySelector("#auditSeverityFilter").addEventListener("change", renderAudit);
document.querySelector("#auditActorFilter").addEventListener("change", renderAudit);

document.querySelector("#dashboardCommandCenter").addEventListener("click", (event) => {
  const filter = event.target.closest(".filter-pill");
  const range = event.target.closest(".range-tabs button");
  if (filter) {
    filter.parentElement.querySelectorAll(".filter-pill").forEach((button) => button.classList.remove("is-active"));
    filter.classList.add("is-active");
  }
  if (range) {
    range.parentElement.querySelectorAll("button").forEach((button) => button.classList.remove("is-active"));
    range.classList.add("is-active");
  }
});

document.querySelector("#requestsTable").addEventListener("click", (event) => {
  const approve = event.target.closest("[data-approve]");
  const refuse = event.target.closest("[data-refuse]");
  const provision = event.target.closest("[data-provision]");
  if (approve) approveRequest(approve.dataset.approve);
  if (refuse) refuseRequest(refuse.dataset.refuse);
  if (provision) provisionRequest(provision.dataset.provision);
});

initApp();
