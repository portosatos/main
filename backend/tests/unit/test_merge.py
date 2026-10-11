"""Merging devices minute by minute, the watch beats the phone (SPEC F4.4, ADR-007): merge.py."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.services.merge import Merged, device_order, merge_hr, merge_steps

pytestmark = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="step 4.2: not implemented"
)

REGISTERED = datetime(2026, 9, 1, tzinfo=UTC)
MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class Dev:
    id: uuid.UUID
    kind: str
    external_id: str
    created_at: datetime


def dev(external_id: str, kind: str, registered_days: int = 0) -> Dev:
    return Dev(uuid.uuid4(), kind, external_id, REGISTERED + timedelta(days=registered_days))


def minutes(start: datetime, count: int) -> list[datetime]:
    return [start + i * MINUTE for i in range(count)]


WALK = minutes(datetime(2026, 10, 1, 8, 0, tzinfo=UTC), 20)


def rank(device: Dev) -> tuple:
    """The priority of SPEC F4.4, lower is stronger: watch first, then the earlier registered.
    Devices registered at the same moment (one meta line) go by external id (assumption)."""
    return (device.kind != "watch", device.created_at, device.external_id)


@st.composite
def fleets(draw: st.DrawFn) -> tuple[list[Dev], dict, dict]:
    """Devices with random kinds and registration times (ties included) and, per device, the
    covered minutes of a 10-minute window and step values on some of them."""
    window = minutes(datetime(2026, 10, 1, 8, 0, tzinfo=UTC), 10)
    count = draw(st.integers(1, 4))
    devices = [
        Dev(
            uuid.uuid4(),
            draw(st.sampled_from(["watch", "phone"])),
            f"device-{i}",
            REGISTERED + timedelta(days=draw(st.integers(0, 2))),
        )
        for i in range(count)
    ]
    coverage = {}
    steps = {}
    for device in devices:
        covered = draw(st.sets(st.sampled_from(window)))
        coverage[device.id] = covered
        with_steps = draw(st.sets(st.sampled_from(sorted(covered)))) if covered else set()
        steps[device.id] = {m: float(draw(st.integers(0, 200))) for m in sorted(with_steps)}
    return devices, coverage, steps


@given(fleets())
def test_merged_minute_single_source_never_sum(fleet: tuple[list[Dev], dict, dict]) -> None:
    devices, coverage, steps = fleet
    merged = merge_steps(device_order(devices), coverage, steps)

    covered = set().union(*coverage.values())
    assert set(merged) == covered  # an uncovered minute has no data, a covered one has a value
    for minute, result in merged.items():
        covering = [d for d in devices if minute in coverage[d.id]]
        expected = min(covering, key=rank)
        assert result.source_device_id == expected.id
        # the value is the source's own: its steps, 0 if it has none in this minute
        assert result.value == steps[expected.id].get(minute, 0.0)
        nonzero = [steps[d.id][minute] for d in covering if steps[d.id].get(minute, 0.0) > 0]
        if len(nonzero) >= 2:
            assert result.value != sum(nonzero)


def test_walk_both_devices_watch_wins_2000() -> None:
    # SPEC §8 stage 4: one walk recorded by both devices, watch 2000 and phone 1900 -> 2000.
    watch, phone = dev("watch-1", "watch"), dev("phone-1", "phone")
    coverage = {watch.id: set(WALK), phone.id: set(WALK)}
    steps = {watch.id: dict.fromkeys(WALK, 100.0), phone.id: dict.fromkeys(WALK, 95.0)}

    merged = merge_steps(device_order([phone, watch]), coverage, steps)

    assert sum(m.value for m in merged.values()) == 2000
    assert {m.source_device_id for m in merged.values()} == {watch.id}


def test_watch_covered_minute_without_steps_is_zero_not_phone() -> None:
    # The watch covers 08:00 with a pulse point only: the minute is 0 from the watch, not the
    # phone's 80; 08:01 is covered by the phone alone and takes its 70.
    watch, phone = dev("watch-1", "watch"), dev("phone-1", "phone")
    m0, m1 = WALK[0], WALK[1]
    coverage = {watch.id: {m0}, phone.id: {m0, m1}}
    steps = {watch.id: {}, phone.id: {m0: 80.0, m1: 70.0}}

    merged = merge_steps(device_order([watch, phone]), coverage, steps)

    assert merged == {m0: Merged(0.0, watch.id), m1: Merged(70.0, phone.id)}


def test_earliest_registered_device_wins_among_same_kind() -> None:
    old_watch = dev("watch-b", "watch", registered_days=0)
    new_watch = dev("watch-a", "watch", registered_days=5)
    old_phone = dev("phone-z", "phone", registered_days=-30)  # older than any watch, still last
    new_phone = dev("phone-y", "phone", registered_days=1)
    # one meta line registers its devices at the same moment: the external id decides
    tie_watch_1 = dev("watch-c", "watch", registered_days=7)
    tie_watch_2 = dev("watch-d", "watch", registered_days=7)

    order = device_order([new_phone, tie_watch_2, new_watch, old_phone, tie_watch_1, old_watch])

    assert order == [
        old_watch.id,
        new_watch.id,
        tie_watch_1.id,
        tie_watch_2.id,
        old_phone.id,
        new_phone.id,
    ]
    m = WALK[0]
    coverage = {d.id: {m} for d in (old_watch, new_watch, old_phone)}
    steps = {old_watch.id: {m: 10.0}, new_watch.id: {m: 50.0}, old_phone.id: {m: 90.0}}
    assert merge_steps(order, coverage, steps) == {m: Merged(10.0, old_watch.id)}


def test_hr_phone_points_only_where_watch_missing() -> None:
    # 08:00: both devices have pulse -> only the watch points; 08:01: the watch has none -> the
    # phone points; 08:02: only the watch.
    watch, phone = dev("watch-1", "watch"), dev("phone-1", "phone")
    m0, m1, m2 = WALK[:3]
    hr = {
        watch.id: {m0: [70, 72], m2: [75]},
        phone.id: {m0: [90, 91, 92], m1: [88]},
    }

    merged = merge_hr(device_order([phone, watch]), hr)

    assert merged == {
        m0: Merged([70, 72], watch.id),
        m1: Merged([88], phone.id),
        m2: Merged([75], watch.id),
    }
