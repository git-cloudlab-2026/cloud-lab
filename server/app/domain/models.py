from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import AuditSeverity, MetricState, NotificationType, RequestStatus, UserRole, VmStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"), nullable=False)
    class_name: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VmTemplate(Base):
    __tablename__ = "vm_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cpu: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_per_hour_chf: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    ansible_playbook: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    course: Mapped[Course] = relationship()


class VmRequest(Base):
    __tablename__ = "vm_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("vm_templates.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[RequestStatus] = mapped_column(SAEnum(RequestStatus, name="request_status"), nullable=False, default=RequestStatus.pending)
    request_reason: Mapped[str | None] = mapped_column(Text)
    validator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    course: Mapped[Course] = relationship()
    template: Mapped[VmTemplate] = relationship()


class VirtualMachine(Base):
    __tablename__ = "virtual_machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("vm_requests.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    provider_vm_id: Mapped[str | None] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[VmStatus] = mapped_column(SAEnum(VmStatus, name="vm_status"), nullable=False, default=VmStatus.creating)
    ssh_username: Mapped[str] = mapped_column(String(80), nullable=False, default="student")
    ssh_key_fingerprint: Mapped[str | None] = mapped_column(String(160))
    network_segment: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship()


class VmMetric(Base):
    __tablename__ = "vm_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vm_id: Mapped[int] = mapped_column(ForeignKey("virtual_machines.id", ondelete="CASCADE"), nullable=False)
    cpu_usage_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ram_usage_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    disk_usage_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    state: Mapped[MetricState] = mapped_column(SAEnum(MetricState, name="metric_state"), nullable=False, default=MetricState.unknown)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vm_id: Mapped[int] = mapped_column(ForeignKey("virtual_machines.id", ondelete="CASCADE"), nullable=False)
    cost_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours_running: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    cost_estimate_chf: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    request_id: Mapped[int | None] = mapped_column(ForeignKey("vm_requests.id", ondelete="SET NULL"))
    vm_id: Mapped[int | None] = mapped_column(ForeignKey("virtual_machines.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[AuditSeverity] = mapped_column(SAEnum(AuditSeverity, name="audit_severity"), nullable=False, default=AuditSeverity.info)
    event_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(SAEnum(NotificationType, name="notification_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
