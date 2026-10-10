"""Devices of an upload: created on first sight, the kind comes from the meta line (SPEC F2, §7.2).

A device listed in meta is created as soon as the meta line is read, so resuming a file after
the meta line (step 3.2) keeps the kinds. A device met in a record without meta is created as a
phone with a warning in the report. Existing devices are never changed by later uploads.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device
from app.services.ingest.parser import DeviceMeta, Meta

UNKNOWN_DEVICE_KIND = "phone"


class DeviceResolver:
    """Maps external ids of the user's devices to device ids, creating the missing ones."""

    def __init__(self, session: AsyncSession, *, user_id: uuid.UUID, now: datetime) -> None:
        self._session = session
        self._user_id = user_id
        self._now = now
        self._ids: dict[str, uuid.UUID] = {}

    async def register(self, meta: Meta) -> None:
        """Create the devices of a meta line that the user does not have yet."""
        new = {d.external_id: d for d in meta.devices if d.external_id not in self._ids}
        await self._create(new.values())
        await self._load(new)

    async def resolve(self, external_ids: Iterable[str]) -> tuple[dict[str, uuid.UUID], list[str]]:
        """Device ids of `external_ids` and warnings about devices created without meta."""
        wanted = set(external_ids)
        await self._load(wanted - self._ids.keys())
        missing = sorted(wanted - self._ids.keys())
        created = await self._create(
            DeviceMeta(external_id, UNKNOWN_DEVICE_KIND, external_id) for external_id in missing
        )
        await self._load(set(missing) - created)
        warnings = [
            f"Устройство «{external_id}» не описано в meta: создано с типом phone"
            for external_id in missing
            if external_id in created
        ]
        return {external_id: self._ids[external_id] for external_id in wanted}, warnings

    async def _create(self, devices: Iterable[DeviceMeta]) -> set[str]:
        """Insert devices the user does not have; returns the external ids actually created."""
        values = [
            {
                "id": uuid.uuid4(),
                "user_id": self._user_id,
                "external_id": d.external_id,
                "kind": d.kind,
                "name": d.name,
                "created_at": self._now,
            }
            for d in devices
        ]
        if not values:
            return set()
        stmt = (
            insert(Device)
            .values(values)
            .on_conflict_do_nothing(index_elements=[Device.user_id, Device.external_id])
            .returning(Device.external_id, Device.id)
        )
        created = (await self._session.execute(stmt)).all()
        self._ids.update({external_id: device_id for external_id, device_id in created})
        return {external_id for external_id, _ in created}

    async def _load(self, external_ids: Iterable[str]) -> None:
        wanted = set(external_ids) - self._ids.keys()
        if not wanted:
            return
        found = await self._session.execute(
            select(Device.external_id, Device.id).where(
                Device.user_id == self._user_id, Device.external_id.in_(wanted)
            )
        )
        self._ids.update({external_id: device_id for external_id, device_id in found.all()})
