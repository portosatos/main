"""Device routes (SPEC F2, §6.3): the user's devices and renaming one.

Devices are created by the ingest; only the name changes here. A rename tells the user's other
tabs with `devices.changed` (SPEC F12).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.auth.deps import CurrentUserDep
from app.models import CoverageMinute, Device
from app.schemas.devices import DeviceOut, DeviceRename
from app.services import events

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _out(device: Device, last_data_at: datetime | None) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        external_id=device.external_id,
        kind=device.kind,
        name=device.name,
        created_at=device.created_at,
        last_data_at=last_data_at,
    )


def _with_last_data(user_id: uuid.UUID) -> Select[tuple[Device, datetime | None]]:
    """The user's devices with the start of their last covered minute."""
    # The (device_id, minute_utc) primary key makes the max per device an index lookup.
    last = (
        select(func.max(CoverageMinute.minute_utc))
        .where(CoverageMinute.device_id == Device.id)
        .scalar_subquery()
    )
    return select(Device, last).where(Device.user_id == user_id)


async def _own_device(session: AsyncSession, user_id: uuid.UUID, device_id: uuid.UUID) -> Device:
    device = await session.scalar(
        select(Device).where(Device.id == device_id, Device.user_id == user_id)
    )
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Устройство не найдено")
    return device


@router.get("")
async def list_devices(user: CurrentUserDep, session: SessionDep) -> list[DeviceOut]:
    """The user's devices in the order of registration, with the time of their last data."""
    rows = await session.execute(
        _with_last_data(user.id).order_by(Device.created_at, Device.external_id)
    )
    return [_out(device, last) for device, last in rows.all()]


@router.patch("/{device_id}")
async def rename_device(
    device_id: uuid.UUID, body: DeviceRename, user: CurrentUserDep, session: SessionDep
) -> DeviceOut:
    """New name of the device; another user's device is 404, as a missing one."""
    device = await _own_device(session, user.id, device_id)
    device.name = body.name
    await events.publish(session, user.id, "devices.changed", {"device_id": str(device.id)})
    await session.commit()
    row = (await session.execute(_with_last_data(user.id).where(Device.id == device_id))).one()
    return _out(*row)
