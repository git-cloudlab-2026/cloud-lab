import cron from "node-cron";
import { query, withTransaction } from "../db/pool.js";
import { createNotification } from "../services/notificationService.js";

export async function createExpiringVmNotifications() {
  const { rows } = await query(`
    SELECT
      vm.vm_id,
      vm.vm_name,
      vm.owner_name,
      vm.end_date,
      u.id AS user_id,
      u.email
    FROM expiring_vms vm
    JOIN virtual_machines m ON m.id = vm.vm_id
    JOIN users u ON u.id = m.owner_id
    WHERE NOT EXISTS (
      SELECT 1
      FROM notifications n
      WHERE n.user_id = u.id
        AND n.type = 'vm_expiring_soon'
        AND n.metadata->>'vm_id' = vm.vm_id::text
        AND n.created_at::date = CURRENT_DATE
    )
  `);

  for (const vm of rows) {
    await createNotification(
      vm.user_id,
      "vm_expiring_soon",
      "Votre VM arrive bientot a echeance",
      `La machine ${vm.vm_name} arrive a echeance le ${vm.end_date}. Pensez a sauvegarder votre travail ou demander une prolongation.`,
      {
        email: vm.email,
        metadata: {
          vm_id: vm.vm_id,
          end_date: vm.end_date
        }
      }
    );
  }

  return rows.length;
}

export async function markExpiredVirtualMachines() {
  return withTransaction(async (client) => {
    const { rows: expiredVms } = await client.query(`
      SELECT
        vm.*,
        u.email AS owner_email
      FROM virtual_machines vm
      JOIN users u ON u.id = vm.owner_id
      WHERE vm.end_date <= CURRENT_DATE
        AND vm.status NOT IN ('expired', 'destroyed')
      FOR UPDATE OF vm
    `);

    for (const vm of expiredVms) {
      await client.query(
        `UPDATE virtual_machines
         SET status = 'expired'
         WHERE id = $1`,
        [vm.id]
      );

      await client.query(
        `INSERT INTO audit_events (actor_id, vm_id, request_id, event_type, severity, event_message)
         VALUES (NULL, $1, $2, 'vm_expired', 'warning', $3)`,
        [vm.id, vm.request_id, `VM #${vm.id} marquee expired automatiquement: end_date ${vm.end_date}. Aucune destruction cloud n'est declenchee.`]
      );

      await createNotification(
        vm.owner_id,
        "vm_expired",
        "Votre VM est arrivee a echeance",
        `La machine ${vm.name} est arrivee a echeance. Elle est maintenant en attente de destruction reelle par le service d'infrastructure.`,
        {
          client,
          email: vm.owner_email,
          metadata: {
            vm_id: vm.id,
            request_id: vm.request_id,
            end_date: vm.end_date
          }
        }
      );
    }

    return expiredVms.length;
  });
}

export function startNotificationJobs() {
  cron.schedule("0 8 * * *", async () => {
    try {
      const expiredCount = await markExpiredVirtualMachines();
      const expiringCount = await createExpiringVmNotifications();
      console.log(`[lifecycle] ${expiredCount} VM marquee(s) expired, ${expiringCount} notification(s) d'echeance proche creee(s).`);
    } catch (error) {
      console.error("[lifecycle] Echec du job de fin de vie VM", error);
    }
  });
}
