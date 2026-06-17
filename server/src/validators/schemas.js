import { z } from "zod";

const dateString = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Date attendue au format YYYY-MM-DD");

export const createUserSchema = z.object({
  full_name: z.string().min(2).max(120),
  email: z.string().email().max(160),
  role: z.enum(["student", "teacher", "validator", "admin"]),
  class_name: z.string().max(80).nullable().optional(),
  is_active: z.boolean().optional()
});

export const createVmRequestSchema = z
  .object({
    requester_id: z.number().int().positive(),
    course_id: z.number().int().positive(),
    template_id: z.number().int().positive(),
    quantity: z.number().int().positive().default(1),
    start_date: dateString,
    end_date: dateString,
    request_reason: z.string().max(2000).nullable().optional()
  })
  .refine((payload) => payload.end_date > payload.start_date, {
    message: "end_date doit etre apres start_date",
    path: ["end_date"]
  });

export const patchVmRequestSchema = z
  .object({
    status: z.enum(["approved", "refused", "provisioning", "provisioned", "failed", "expired", "destroyed"]),
    validator_id: z.number().int().positive().optional(),
    decision_comment: z.string().min(1).max(2000).optional()
  })
  .refine((payload) => {
    if (!["approved", "refused"].includes(payload.status)) return true;
    return Boolean(payload.validator_id && payload.decision_comment);
  }, {
    message: "validator_id et decision_comment sont obligatoires pour approved/refused",
    path: ["decision_comment"]
  });

export const patchVirtualMachineSchema = z.object({
  status: z.enum(["creating", "running", "stopped", "down", "expired", "destroyed", "error"]),
  actor_id: z.number().int().positive().nullable().optional()
});

export const provisioningResultSchema = z.object({
  provider_vm_id: z.string().min(1).max(120),
  ip_address: z.string().min(3).max(60).nullable().optional(),
  status: z.enum(["running", "error"]),
  network_segment: z.string().max(80).nullable().optional()
});

export const destructionResultSchema = z.object({
  status: z.literal("destroyed"),
  destroyed_at: z.string().datetime().optional()
});
