"""Records of the watch and the phone for one day profile (SPEC F13).

Watch: steps per minute of being awake (zeros included), pulse every --hr-interval seconds,
sleep. Phone: steps in 5-minute intervals of being awake, sleep with a +-20 minute error,
no pulse. Steps intervals of one device follow each other and never overlap.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

from htgen.config import PHONE, WATCH, Config, Device
from htgen.profile import SITTING, SLEEP, WALK, DayProfile, rng
from htgen.timeline import Timeline

WATCH_STEPS = timedelta(minutes=1)
PHONE_STEPS = timedelta(minutes=5)
UNALIGNED_SHIFT = (1, 59)  # seconds
TYPE_ORDER = {"sleep": 0, "steps": 1, "hr": 2}

Line = tuple[datetime, int, str, str]  # sort key (moment, type, device) and the NDJSON line


def _steps(
    profile: DayProfile, device: Device, length: timedelta, offset: timedelta, timeline: Timeline
) -> Iterator[Line]:
    phone = device == PHONE
    for segment_start, segment_end in profile.awake_segments():
        start = segment_start + offset
        while start + length <= segment_end:
            end = start + length
            count = round(profile.steps_between(start, end, phone=phone))
            yield (
                start,
                TYPE_ORDER["steps"],
                device.id,
                f'{{"type":"steps","device":"{device.id}","start":"{timeline.iso(start)}",'
                f'"end":"{timeline.iso(end)}","count":{count}}}',
            )
            start = end


def _sleep(
    spans: list[tuple[datetime, datetime]], device: Device, timeline: Timeline
) -> Iterator[Line]:
    for start, end in spans:
        yield (
            start,
            TYPE_ORDER["sleep"],
            device.id,
            f'{{"type":"sleep","device":"{device.id}","start":"{timeline.iso(start)}",'
            f'"end":"{timeline.iso(end)}"}}',
        )


def _pulse(profile: DayProfile, config: Config, timeline: Timeline) -> Iterator[Line]:
    r = rng(config.seed, profile.day, "hr")
    rest = profile.resting_hr
    step = timedelta(seconds=config.hr_interval)
    moment = profile.start
    while moment < profile.end:
        i = profile.minute(moment)
        state, cadence = profile.state[i], profile.cadence[i]
        if state == SLEEP:
            bpm = rest - 8
        elif state == WALK:
            bpm = 95 + (cadence - 95) * 0.8
        elif state == SITTING:
            bpm = rest + 2
        else:  # LIGHT
            bpm = rest + 6 + cadence * 0.4
        bpm = min(max(round(bpm + r.gauss(0, 2)), 40), 190)
        yield (
            moment,
            TYPE_ORDER["hr"],
            WATCH.id,
            f'{{"type":"hr","device":"{WATCH.id}","ts":"{timeline.iso(moment)}","bpm":{bpm}}}',
        )
        moment += step


def day_lines(profile: DayProfile, config: Config, timeline: Timeline) -> list[str]:
    """NDJSON lines of one date in time order (sleep, steps, pulse at the same moment)."""
    offset = timedelta(0)
    if config.unaligned:  # the same shift of the grid for both devices, e.g. 08:00:30
        offset = timedelta(seconds=rng(config.seed, profile.day, "align").randint(*UNALIGNED_SHIFT))
    lines: list[Line] = []
    if config.has(WATCH):
        lines += _sleep(profile.sleep, WATCH, timeline)
        lines += _steps(profile, WATCH, WATCH_STEPS, offset, timeline)
        lines += _pulse(profile, config, timeline)
    if config.has(PHONE):
        lines += _sleep(profile.phone_sleep, PHONE, timeline)
        lines += _steps(profile, PHONE, PHONE_STEPS, offset, timeline)
    lines.sort(key=lambda line: line[:3])
    return [line[3] for line in lines]
