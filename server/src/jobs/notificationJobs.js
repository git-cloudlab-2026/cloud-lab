import cron from "node-cron";
import { query } from "../db/pool.js";
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

export function startNotificationJobs() {
  cron.schedule("0 8 * * *", async () => {
    try {
      const count = await createExpiringVmNotifications();
      console.log(`[notifications] ${count} notification(s) VM expiration creee(s).`);
    } catch (error) {
      console.error("[notifications] Echec du job VM expiration", error);
    }
  });
}

