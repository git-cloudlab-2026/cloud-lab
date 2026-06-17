import { pool, query } from "../src/db/pool.js";

function randomPercent(min, max) {
  return Number((Math.random() * (max - min) + min).toFixed(2));
}

function randomState() {
  return Math.random() > 0.08 ? "up" : "unknown";
}

async function main() {
  const { rows: vms } = await query(
    `SELECT id, name
     FROM virtual_machines
     WHERE status = 'running'
     ORDER BY id`
  );

  if (vms.length === 0) {
    console.log("[simulate-metrics] Aucune VM running trouvee.");
    return;
  }

  for (const vm of vms) {
    const metric = {
      cpu: randomPercent(8, 78),
      ram: randomPercent(18, 86),
      disk: randomPercent(22, 74),
      state: randomState()
    };

    await query(
      `INSERT INTO vm_metrics (vm_id, cpu_usage_percent, ram_usage_percent, disk_usage_percent, state)
       VALUES ($1, $2, $3, $4, $5)`,
      [vm.id, metric.cpu, metric.ram, metric.disk, metric.state]
    );

    console.log(`[simulate-metrics] VM #${vm.id} ${vm.name}: cpu=${metric.cpu}% ram=${metric.ram}% disk=${metric.disk}% state=${metric.state}`);
  }
}

try {
  await main();
} finally {
  await pool.end();
}

