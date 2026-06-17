import { Router } from "express";
import { listCostRecords, listCourses, listVmMetrics, listVmTemplates } from "../controllers/common-controller.js";
import { listAuditEvents } from "../controllers/audit-events-controller.js";
import { getDashboardSummary } from "../controllers/dashboard-controller.js";
import { createUser, listUsers } from "../controllers/users-controller.js";
import { createVmRequest, listVmRequests, patchVmRequest } from "../controllers/vm-requests-controller.js";
import { listVirtualMachines, patchVirtualMachine } from "../controllers/virtual-machines-controller.js";
import { asyncHandler } from "../middlewares/async-handler.js";
import { validateBody } from "../middlewares/validate.js";
import { createUserSchema, createVmRequestSchema, patchVirtualMachineSchema, patchVmRequestSchema } from "../validators/schemas.js";

export const apiRouter = Router();

apiRouter.get("/users", asyncHandler(listUsers));
apiRouter.post("/users", validateBody(createUserSchema), asyncHandler(createUser));

apiRouter.get("/courses", asyncHandler(listCourses));
apiRouter.get("/vm-templates", asyncHandler(listVmTemplates));

apiRouter.get("/vm-requests", asyncHandler(listVmRequests));
apiRouter.post("/vm-requests", validateBody(createVmRequestSchema), asyncHandler(createVmRequest));
apiRouter.patch("/vm-requests/:id", validateBody(patchVmRequestSchema), asyncHandler(patchVmRequest));

apiRouter.get("/virtual-machines", asyncHandler(listVirtualMachines));
apiRouter.patch("/virtual-machines/:id", validateBody(patchVirtualMachineSchema), asyncHandler(patchVirtualMachine));

apiRouter.get("/vm-metrics", asyncHandler(listVmMetrics));
apiRouter.get("/cost-records", asyncHandler(listCostRecords));
apiRouter.get("/audit-events", asyncHandler(listAuditEvents));

apiRouter.get("/dashboard/summary", asyncHandler(getDashboardSummary));
