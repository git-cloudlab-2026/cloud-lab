from enum import Enum


class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"
    validator = "validator"
    admin = "admin"


class RequestStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    refused = "refused"
    provisioning = "provisioning"
    provisioned = "provisioned"
    failed = "failed"
    expired = "expired"
    destroyed = "destroyed"


class VmStatus(str, Enum):
    creating = "creating"
    running = "running"
    stopped = "stopped"
    down = "down"
    expired = "expired"
    destroyed = "destroyed"
    error = "error"


class MetricState(str, Enum):
    up = "up"
    down = "down"
    unknown = "unknown"


class AuditSeverity(str, Enum):
    info = "info"
    success = "success"
    warning = "warning"
    danger = "danger"


class NotificationType(str, Enum):
    vm_request_approved = "vm_request_approved"
    vm_request_refused = "vm_request_refused"
    vm_expiring_soon = "vm_expiring_soon"
    vm_expired = "vm_expired"
    vm_destroyed = "vm_destroyed"
