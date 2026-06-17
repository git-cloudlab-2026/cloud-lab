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
  - les fonctions query.* evitent de dupliquer la logique dans chaque vue.
*/

const STORAGE_KEY = "git-cloud-lab-control-center-v3";
const CLOCK_NOW = "2026-06-17T10:00:00";
const EXPIRING_THRESHOLD_HOURS = 24;

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
    { id: 1, fullName: "Nadia Keller", email: "nadia.keller@git.example", role: "validator", className: "" },
    { id: 2, fullName: "Marc Dubois", email: "marc.dubois@git.example", role: "trainer", className: "" },
    { id: 3, fullName: "Amir Benali", email: "amir.benali@git.example", role: "student", className: "IT-2026-A" },
    { id: 4, fullName: "Sara Nguyen", email: "sara.nguyen@git.example", role: "student", className: "IT-2026-A" },
    { id: 5, fullName: "Leo Martin", email: "leo.martin@git.example", role: "student", className: "IT-2026-B" },
    { id: 6, fullName: "Administrateur Lab", email: "admin@git.example", role: "admin", className: "" }
  ],
  courses: [
    { id: 1, slug: "linux-admin", name: "Administration Linux", className: "IT-2026-A", budgetChf: 160 },
    { id: 2, slug: "dev-web", name: "Developpement Web", className: "IT-2026-A", budgetChf: 180 },
    { id: 3, slug: "data-science", name: "Data Science", className: "IT-2026-B", budgetChf: 260 },
    { id: 4, slug: "securite", name: "Cybersecurity Lab", className: "IT-2026-C", budgetChf: 220 }
  ],
  templates: [
    {
      id: 1,
      slug: "linux-admin",
      courseId: 1,
      name: "Linux Admin",
      description: "Ubuntu LTS avec outils systeme, SSH securise et nginx.",
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
      name: "Dev Web",
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
      name: "Data Science",
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
      name: "Cybersecurity Lab",
      description: "VM isolee avec outils securite autorises pour laboratoire.",
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
      decisionComment: "Duree trop longue pour le pilote.",
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
      decisionComment: "OK, duree courte et cout maitrise.",
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
      decisionComment: "Environnement ferme apres echeance.",
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
      reason: "Test de reprise apres erreur provisioning",
      validatorId: 1,
      decisionComment: "Erreur conservee pour demontrer le suivi.",
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
    "2026-06-17 08:20 - Demande groupee Linux Admin enregistree.",
    "2026-06-16 13:40 - Demande Dev Web approuvee.",
    "2026-06-13 10:14 - VM git-linux-admin-amir-001 active.",
    "2026-06-11 15:24 - VM git-cyber-amir-001 provisionnee.",
    "2026-06-16 00:00 - VM git-cyber-amir-001 arrivee a expiration."
  ]
};

let state = normaliseState(loadState());
refreshLifecycleStatuses();

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return structuredClone(seed);
  try {
    return JSON.parse(raw);
  } catch {
    return structuredClone(seed);
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function normaliseState(input) {
  const data = structuredClone(input);
  data.users ||= [];
  data.courses ||= [];
  data.templates ||= [];
  data.requests ||= [];
  data.vms ||= [];
  data.events ||= [];

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
    if (vm.status === "running") vm.status = "active";
  });

  return data;
}

function byId(list, id) {
  return list.find((item) => item.id === Number(id));
}

function nowDate() {
  return new Date(CLOCK_NOW);
}

function toDate(value) {
  if (!value) return null;
  return new Date(value.includes("T") ? value : `${value}T00:00:00`);
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
    addEvent(`Transition refusee: ${entity.status} -> ${nextStatus} pour #${entity.id}.`);
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
  const invalidDates = state.requests.filter((request) => toDate(request.endDate) <= toDate(request.startDate)).length;
  const missingVmEndDate = state.vms.filter((vm) => !vm.endDate && vm.status !== "destroyed").length;
  const missingCostTemplate = state.requests.filter((request) => !templateForRequest(request)).length;
  const pendingProvisioning = query.requests({ status: "approved" }).length;
  const expiredToDestroy = query.vms({ status: "expired" }).length;
  const totalReal = state.vms.reduce((sum, vm) => sum + realVmCost(vm), 0);
  const totalCommitted = state.requests
    .filter((request) => ["pending", "approved"].includes(request.status))
    .reduce((sum, request) => sum + estimatedRequestCost(request), 0);
  const totalBudget = state.courses.reduce((sum, course) => sum + course.budgetChf, 0);

  return [
    {
      label: "Modele prix",
      value: "Infomaniak",
      detail: `Base ${formatCost(PRICING_MODEL.referenceMonthlyChf)}/mois pour ${PRICING_MODEL.referenceCpu} CPU, ${PRICING_MODEL.referenceRamGb} GB RAM, ${PRICING_MODEL.referenceDiskGb} GB disque.`,
      tone: "success"
    },
    {
      label: "Dates de fin",
      value: missingVmEndDate === 0 && invalidDates === 0 ? "OK" : `${missingVmEndDate + invalidDates} anomalie(s)`,
      detail: "Aucune VM active sans echeance.",
      tone: missingVmEndDate === 0 && invalidDates === 0 ? "success" : "danger"
    },
    {
      label: "Catalogue couts",
      value: missingCostTemplate === 0 ? "OK" : `${missingCostTemplate} template manquant`,
      detail: "Chaque demande utilise un template avec cout/h.",
      tone: missingCostTemplate === 0 ? "success" : "danger"
    },
    {
      label: "Provisioning",
      value: pendingProvisioning,
      detail: "Demande(s) approuvee(s) prete(s) a envoyer a Terraform.",
      tone: pendingProvisioning > 0 ? "warning" : "neutral"
    },
    {
      label: "Nettoyage",
      value: expiredToDestroy,
      detail: "VM expiree(s) a detruire pour stopper les couts.",
      tone: expiredToDestroy > 0 ? "warning" : "success"
    },
    {
      label: "Budget consomme",
      value: `${budgetPercent({ budgetChf: totalBudget }, totalReal, totalCommitted)}%`,
      detail: `${formatCost(totalReal)} reels + ${formatCost(totalCommitted)} engages sur ${formatCost(totalBudget)}.`,
      tone: (totalReal + totalCommitted) / totalBudget > 0.8 ? "danger" : "success"
    }
  ];
}

function statusBadge(status) {
  const labels = {
    pending: "En attente",
    approved: "Approuvee",
    provisioning: "Provisioning",
    active: "Active",
    expiring: "Expire bientot",
    expired: "Expiree",
    destroyed: "Detruite",
    refused: "Refusee",
    error: "Erreur"
  };
  return `<span class="badge status-${status}">${labels[status] || status}</span>`;
}

function addEvent(message) {
  const stamp = new Date(CLOCK_NOW).toLocaleString("fr-CH");
  state.events.unshift(`${stamp} - ${message}`);
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
      if (filters.status && vm.status !== filters.status) return false;
      if (filters.courseId && request.courseId !== Number(filters.courseId)) return false;
      if (filters.userId && vm.ownerId !== Number(filters.userId)) return false;
      if (filters.from && toDate(vm.createdAt) < toDate(filters.from)) return false;
      if (filters.to && toDate(vm.createdAt) > toDate(filters.to)) return false;
      return true;
    });
  },
  alerts() {
    return state.vms
      .map((vm) => {
        const owner = byId(state.users, vm.ownerId);
        const left = hoursUntil(vm.endDate);
        if (vm.status === "destroyed") return null;
        if (vm.status === "expired" || left < 0) return { vm, owner, label: "A detruire", tone: "red" };
        if (vm.status === "error") return { vm, owner, label: "Erreur technique", tone: "red" };
        if (left <= EXPIRING_THRESHOLD_HOURS) return { vm, owner, label: `Expire dans ${Math.max(0, Math.ceil(left))}h`, tone: "amber" };
        return null;
      })
      .filter(Boolean);
  },
  costByCourse() {
    return state.courses.map((course) => {
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
    state.courses.forEach((course) => {
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
    const activeVms = query.vms().filter((vm) => ["active", "expiring"].includes(vm.status)).length;
    const pending = query.requests({ status: "pending" }).length;
    const expired = query.vms({ status: "expired" }).length;
    const error = query.vms({ status: "error" }).length;
    const destroyed = query.vms({ status: "destroyed" }).length;
    const realCost = state.vms.reduce((sum, vm) => sum + realVmCost(vm), 0);
    return [
      ["VM actives", activeVms, "success"],
      ["Demandes en attente", pending, "warning"],
      ["VM expirees", expired, "danger"],
      ["VM en erreur", error, "danger"],
      ["VM detruites", destroyed, "neutral"],
      ["Cout reel actuel", formatCost(realCost), "accent"]
    ];
  }
};

function setView(viewName) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelector(`#view-${viewName}`).classList.add("active");
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
}

function renderKpis() {
  document.querySelector("#kpiGrid").innerHTML = query.kpis()
    .map(([label, value, tone]) => {
      const featuredClass = label === "Cout reel actuel" ? " kpi-featured" : "";
      return `<div class="kpi kpi-${tone}${featuredClass}"><span>${label}</span><strong>${value}</strong></div>`;
    })
    .join("");
}

function renderCatalog() {
  document.querySelector("#templateGrid").innerHTML = state.templates
    .map((template) => {
      const course = byId(state.courses, template.courseId);
      return `
        <article class="template-card">
          <h3>${template.name}</h3>
          <p>${template.description}</p>
          <div class="template-meta">
            <span class="badge">${course.name}</span>
            <span class="badge">${template.flavor.name}</span>
            <span class="badge">${template.flavor.cpu} CPU</span>
            <span class="badge">${template.flavor.ramGb} GB RAM</span>
            <span class="badge">${template.flavor.diskGb} GB disque</span>
            <span class="badge">${template.image}</span>
            <span class="badge status-active">${formatHourlyCost(template.hourlyCostChf)}</span>
            <span class="badge status-approved">${formatCost(template.monthlyCostChf)}/mois calcule</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderSelectors() {
  const requesterSelect = document.querySelector("#requesterId");
  requesterSelect.innerHTML = state.users
    .filter((user) => ["student", "trainer"].includes(user.role))
    .map((user) => `<option value="${user.id}">${user.fullName} - ${user.role}</option>`)
    .join("");

  const templateSelect = document.querySelector("#templateId");
  templateSelect.innerHTML = state.templates
    .map((template) => {
      const course = byId(state.courses, template.courseId);
      return `<option value="${template.id}">${template.name} - ${course.name}</option>`;
    })
    .join("");

  document.querySelector("#startDate").value ||= "2026-06-17";
  document.querySelector("#endDate").value ||= "2026-06-24";
}

function renderRequests() {
  document.querySelector("#requestsTable").innerHTML = query.requests()
    .map((request) => {
      const user = ownerForRequest(request);
      const course = courseForRequest(request);
      const template = templateForRequest(request);
      const actions =
        request.status === "pending"
          ? `<button class="action-button approve" data-approve="${request.id}">Approuver</button><button class="action-button refuse" data-refuse="${request.id}">Refuser</button>`
          : "-";
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
          <td>${actions}</td>
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
                <span>${owner.fullName} - fin ${vm.endDate} - cout reel ${formatCost(realVmCost(vm))}</span>
              </div>
              <span class="badge status-${tone === "red" ? "error" : "expiring"}">${label}</span>
            </div>
          `)
          .join("");
}

function renderCourseCosts() {
  document.querySelector("#courseCosts").innerHTML = query.costByCourse()
    .map(({ course, requestCount, committed, real, remaining, percent }) => `
      <div class="list-item cost-row">
        <div>
          <strong>${course.name}</strong>
          <span>${course.className} - ${requestCount} demande(s) - estime en attente ${formatCost(committed)} - engage reel ${formatCost(real)} - reste ${formatCost(remaining)}</span>
          <div class="meter" aria-label="Budget consomme ${percent}%">
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
    ["Approuvees", query.requests({ status: "approved" }).length],
    ["Provisioning", query.requests({ status: "provisioning" }).length],
    ["Actives", query.vms().filter((vm) => ["active", "expiring"].includes(vm.status)).length],
    ["Expirees", query.vms({ status: "expired" }).length],
    ["Detruites", query.vms({ status: "destroyed" }).length]
  ];
  document.querySelector("#lifecycleList").innerHTML = steps
    .map(([label, count]) => `
      <div class="list-item">
        <div>
          <strong>${label}</strong>
          <span>Etape du cycle de vie</span>
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
          <strong>Audit</strong>
          <span>${event}</span>
        </div>
      </div>
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
  document.querySelector("#requestEstimate").textContent = `Cout estime : ${formatCost(cost)}`;
}

function createRequest(event) {
  event.preventDefault();
  const template = byId(state.templates, document.querySelector("#templateId").value);
  const startDate = document.querySelector("#startDate").value;
  const endDate = document.querySelector("#endDate").value;
  if (new Date(endDate) <= new Date(startDate)) {
    alert("La date de fin doit etre apres la date de debut.");
    return;
  }
  const request = {
    id: Math.max(...state.requests.map((item) => item.id), 0) + 1,
    requesterId: Number(document.querySelector("#requesterId").value),
    courseId: template.courseId,
    templateId: template.id,
    quantity: Number(document.querySelector("#quantity").value),
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
  addEvent(`Nouvelle demande #${request.id} enregistree pour validation.`);
  saveState();
  renderAll();
  setView("validation");
  event.target.reset();
  renderSelectors();
  updateEstimate();
}

function approveRequest(id) {
  const request = byId(state.requests, id);
  if (!transitionEntity(request, "approved", "approvedAt")) return;
  request.validatorId = 1;
  request.decisionComment = "Demande approuvee.";
  addEvent(`Demande #${request.id} approuvee. Provisioning pret a demarrer.`);
  saveState();
  renderAll();
}

function refuseRequest(id) {
  const request = byId(state.requests, id);
  if (!transitionEntity(request, "refused", null)) return;
  request.validatorId = 1;
  request.decisionComment = "Demande refusee.";
  addEvent(`Demande #${request.id} refusee.`);
  saveState();
  renderAll();
}

function simulateProvisioning() {
  const request = state.requests.find((item) => item.status === "approved");
  if (!request) {
    alert("Aucune demande approuvee a provisionner.");
    return;
  }
  const owner = ownerForRequest(request);
  const template = templateForRequest(request);
  const course = courseForRequest(request);
  if (!transitionEntity(request, "provisioning", "provisioningAt")) return;
  const firstVmId = Math.max(...state.vms.map((item) => item.id), 0) + 1;
  const slug = owner.fullName.toLowerCase().split(" ")[0];
  const network = owner.className ? owner.className.toLowerCase() : `course-${request.courseId}`;
  const createdVms = [];

  for (let index = 0; index < request.quantity; index += 1) {
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
      createdAt: CLOCK_NOW,
      provisionedAt: null,
      startDate: request.startDate,
      endDate: request.endDate,
      destroyedAt: null
    };
    state.vms.push(vm);
    transitionEntity(vm, "active", "provisionedAt");
    createdVms.push(vm);
  }

  transitionEntity(request, "active", "provisionedAt");
  refreshLifecycleStatuses();
  addEvent(`${createdVms.length} VM provisionnee(s) pour la demande #${request.id} (${template.name}, ${owner.className || course.className}).`);
  saveState();
  renderAll();
}

function destroyExpiredVms() {
  const expired = state.vms.filter((vm) => vm.status === "expired");
  if (expired.length === 0) {
    alert("Aucune VM expiree a detruire.");
    return;
  }
  expired.forEach((vm) => {
    transitionEntity(vm, "destroyed", "destroyedAt");
    const request = byId(state.requests, vm.requestId);
    if (request && canTransition(request.status, "destroyed")) transitionEntity(request, "destroyed", "destroyedAt");
    addEvent(`VM ${vm.name} detruite apres expiration. Cout reel: ${formatCost(realVmCost(vm))}.`);
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
  addEvent("Export CSV des demandes genere.");
  saveState();
  renderAll();
}

function exportVms() {
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
  addEvent("Export CSV des VM genere.");
  saveState();
  renderAll();
}

function renderAll() {
  refreshLifecycleStatuses();
  renderKpis();
  renderCatalog();
  renderSelectors();
  renderRequests();
  renderVms();
  renderAlerts();
  renderCourseCosts();
  renderLifecycle();
  renderEvents();
  renderDataControls();
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
  localStorage.removeItem(STORAGE_KEY);
  state = structuredClone(seed);
  renderAll();
});

document.querySelector("#requestsTable").addEventListener("click", (event) => {
  const approve = event.target.closest("[data-approve]");
  const refuse = event.target.closest("[data-refuse]");
  if (approve) approveRequest(approve.dataset.approve);
  if (refuse) refuseRequest(refuse.dataset.refuse);
});

renderAll();
updateEstimate();
