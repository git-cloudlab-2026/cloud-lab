import { Router } from "express";
import { listCostRecords, listCourses, listVmMetrics, listVmTemplates } from "../controllers/common-controller.js";
import { listAuditEvents } from "../controllers/audit-events-controller.js";
import { getDashboardSummary } from "../controllers/dashboard-controller.js";
import { getNotifications, markRead } from "../controllers/notifications-controller.js";
import { createUser, listUsers } from "../controllers/users-controller.js";
import { createVmRequest, listVmRequests, patchVmRequest, requestProvisioning } from "../controllers/vm-requests-controller.js";
import { listVirtualMachines, patchDestructionResult, patchProvisioningResult, patchVirtualMachine } from "../controllers/virtual-machines-controller.js";
import { asyncHandler } from "../middlewares/async-handler.js";
import { requireAuth, requireRole } from "../middlewares/auth.js";
import { validateBody } from "../middlewares/validate.js";
import { authRouter } from "./auth-routes.js";
import {
  createUserSchema,
  createVmRequestSchema,
  destructionResultSchema,
  patchVirtualMachineSchema,
  patchVmRequestSchema,
  provisioningResultSchema
} from "../validators/schemas.js";

export const apiRouter = Router();

apiRouter.use("/auth", authRouter);
apiRouter.use(requireAuth);

apiRouter.get("/users", asyncHandler(listUsers));
apiRouter.post("/users", requireRole("admin"), validateBody(createUserSchema), asyncHandler(createUser));

apiRouter.get("/courses", asyncHandler(listCourses));
apiRouter.get("/vm-templates", asyncHandler(listVmTemplates));

apiRouter.get("/vm-requests", asyncHandler(listVmRequests));
apiRouter.post("/vm-requests", validateBody(createVmRequestSchema), asyncHandler(createVmRequest));
apiRouter.patch("/vm-requests/:id", requireRole("validator", "admin"), validateBody(patchVmRequestSchema), asyncHandler(patchVmRequest));
apiRouter.post("/vm-requests/:id/provision", requireRole("validator", "admin"), asyncHandler(requestProvisioning));

apiRouter.get("/virtual-machines", asyncHandler(listVirtualMachines));
apiRouter.patch("/virtual-machines/:id", requireRole("validator", "admin"), validateBody(patchVirtualMachineSchema), asyncHandler(patchVirtualMachine));
apiRouter.patch("/virtual-machines/:id/provisioning-result", requireRole("admin"), validateBody(provisioningResultSchema), asyncHandler(patchProvisioningResult));
apiRouter.patch("/virtual-machines/:id/destruction-result", requireRole("admin"), validateBody(destructionResultSchema), asyncHandler(patchDestructionResult));

apiRouter.get("/vm-metrics", asyncHandler(listVmMetrics));
apiRouter.get("/cost-records", asyncHandler(listCostRecords));
apiRouter.get("/audit-events", asyncHandler(listAuditEvents));

apiRouter.get("/notifications", asyncHandler(getNotifications));
apiRouter.patch("/notifications/:id/read", asyncHandler(markRead));

apiRouter.get("/dashboard/summary", asyncHandler(getDashboardSummary));
