from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.domain.enums import AuditSeverity, MetricState, NotificationType, RequestStatus, UserRole, VmStatus


class ApiResponse(BaseModel):
    data: Any


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    class_name: str | None = None
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: UserRole
    class_name: str | None = Field(default=None, max_length=80)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    teacher_id: int | None = None
    created_at: datetime


class VmTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    name: str
    description: str | None = None
    cpu: int
    ram_gb: int
    disk_gb: int
    estimated_cost_per_hour_chf: Decimal
    ansible_playbook: str
    is_active: bool


class VmRequestCreate(BaseModel):
    requester_id: int
    course_id: int
    template_id: int
    quantity: int = Field(default=1, ge=1, le=50)
    start_date: date
    end_date: date
    request_reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("La date de fin doit être postérieure à la date de début.")
        return self


class VmRequestPatch(BaseModel):
    status: RequestStatus
    validator_id: int | None = None
    decision_comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_decision(self):
        if self.status in {RequestStatus.approved, RequestStatus.refused}:
            if not self.validator_id or not self.decision_comment:
                raise ValueError("validator_id et decision_comment sont obligatoires pour approuver ou refuser.")
        return self


class VmRequestReject(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class VmRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int
    course_id: int
    template_id: int
    quantity: int
    start_date: date
    end_date: date
    status: RequestStatus
    request_reason: str | None = None
    validator_id: int | None = None
    decision_comment: str | None = None
    created_at: datetime
    updated_at: datetime


class VirtualMachinePatch(BaseModel):
    status: VmStatus


class ProvisioningResult(BaseModel):
    provider_vm_id: str | None = None
    ip_address: str | None = None
    status: VmStatus
    network_segment: str | None = None


class DestructionResult(BaseModel):
    status: VmStatus = VmStatus.destroyed
    destroyed_at: datetime | None = None


class VirtualMachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    owner_id: int
    provider_vm_id: str | None = None
    name: str
    ip_address: str | None = None
    status: VmStatus
    ssh_username: str
    ssh_key_fingerprint: str | None = None
    network_segment: str | None = None
    created_at: datetime
    start_date: date
    end_date: date
    destroyed_at: datetime | None = None


class VmMetricCreate(BaseModel):
    cpu_usage_percent: Decimal | None = Field(default=None, ge=0, le=100)
    ram_usage_percent: Decimal | None = Field(default=None, ge=0, le=100)
    disk_usage_percent: Decimal | None = Field(default=None, ge=0, le=100)
    state: MetricState = MetricState.unknown


class VmMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vm_id: int
    cpu_usage_percent: Decimal | None = None
    ram_usage_percent: Decimal | None = None
    disk_usage_percent: Decimal | None = None
    state: MetricState
    collected_at: datetime


class CostRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vm_id: int
    cost_date: date
    hours_running: Decimal
    cost_estimate_chf: Decimal


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None = None
    request_id: int | None = None
    vm_id: int | None = None
    event_type: str
    severity: AuditSeverity
    event_message: str
    created_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime
