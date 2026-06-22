from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.common import VmRequestCreate


def test_vm_request_create_accepts_valid_dates():
    today = date.today()

    payload = VmRequestCreate(
        requester_id=1,
        course_id=1,
        template_id=1,
        quantity=1,
        start_date=today,
        end_date=today + timedelta(days=2),
    )

    assert payload.end_date > payload.start_date


def test_vm_request_create_rejects_invalid_dates():
    today = date.today()

    with pytest.raises(ValidationError):
        VmRequestCreate(
            requester_id=1,
            course_id=1,
            template_id=1,
            quantity=1,
            start_date=today,
            end_date=today,
        )
