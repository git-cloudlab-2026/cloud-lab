from fastapi import APIRouter

from app.api.v1.routes import (
    audit_events,
    auth,
    common,
    dashboard,
    notifications,
    users,
    virtual_machines,
    vm_requests,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(common.router, tags=["catalog"])
api_router.include_router(vm_requests.router, prefix="/vm-requests", tags=["vm-requests"])
api_router.include_router(virtual_machines.router, prefix="/virtual-machines", tags=["virtual-machines"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(audit_events.router, prefix="/audit-events", tags=["audit-events"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
