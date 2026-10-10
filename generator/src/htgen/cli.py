"""Command line interface: htgen --days 7 --seed 1 --out sample.ndjson"""

from __future__ import annotations

import argparse
import errno
import io
import os
import sys
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import TextIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from htgen import GENERATOR
from htgen.config import DEFAULT_DAYS, DEFAULT_TZ, DEVICES, Config, Device
from htgen.devices import day_lines
from htgen.ndjson import meta_line
from htgen.profile import plan_day
from htgen.timeline import Timeline


def resolve_period(
    start: date | None, end: date | None, days: int | None, today: date
) -> tuple[date, date]:
    """Inclusive local dates [first, last] of the generated period."""
    if start is not None and end is not None and days is not None:
        raise ValueError("укажите не больше двух из --start, --end, --days")
    if days is not None and days < 1:
        raise ValueError("--days должно быть не меньше 1")
    if start is not None and end is not None:
        if end < start:
            raise ValueError("--end раньше --start")
        return start, end
    length = timedelta(days=(days or DEFAULT_DAYS) - 1)
    if start is not None:
        return start, start + length
    if end is None:
        end = today - timedelta(days=1)  # the last full day: no data from the future
    return end - length, end


def _devices(value: str) -> tuple[Device, ...]:
    kinds = [kind.strip() for kind in value.split(",") if kind.strip()]
    unknown = [kind for kind in kinds if kind not in DEVICES]
    if not kinds or unknown:
        raise argparse.ArgumentTypeError(f"ожидается watch, phone или watch,phone: {value!r}")
    return tuple(device for kind, device in DEVICES.items() if kind in kinds)


def _zone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise argparse.ArgumentTypeError(f"неизвестный часовой пояс IANA: {value!r}") from None
    return value


def _tz_change(value: str) -> tuple[datetime, str]:
    moment, sep, zone = value.partition("=")
    try:
        instant = datetime.fromisoformat(moment)
    except ValueError:
        instant = None
    if not sep or instant is None or instant.tzinfo is None:
        raise argparse.ArgumentTypeError(
            f"ожидается МОМЕНТ=ПОЯС, момент со смещением: 2026-10-05T12:00Z=America/New_York, "
            f"а не {value!r}"
        )
    return instant, _zone(zone)


def _hr_interval(value: str) -> int:
    seconds = int(value)
    if not 1 <= seconds <= 3600:
        raise argparse.ArgumentTypeError("--hr-interval: от 1 до 3600 секунд")
    return seconds


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="htgen",
        description="Генератор тестовой телеметрии в NDJSON (docs/DATA_FORMAT.md).",
    )
    parser.add_argument("--version", action="version", version=GENERATOR)
    period = parser.add_argument_group(
        "период",
        f"локальные даты включительно; без дат — {DEFAULT_DAYS} дней, только --days — до вчера",
    )
    period.add_argument("--start", type=date.fromisoformat, help="первый день, YYYY-MM-DD")
    period.add_argument("--end", type=date.fromisoformat, help="последний день, YYYY-MM-DD")
    period.add_argument("--days", type=int, help="число дней")
    parser.add_argument(
        "--devices",
        type=_devices,
        default=_devices("watch,phone"),
        help="устройства через запятую (по умолчанию watch,phone)",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed (по умолчанию 0)")
    parser.add_argument(
        "--hr-interval",
        type=_hr_interval,
        default=5,
        metavar="SECONDS",
        help="шаг пульса часов в секундах (по умолчанию 5)",
    )
    parser.add_argument(
        "--unaligned",
        action="store_true",
        help="границы интервалов шагов не на начале минуты (например, 08:00:30)",
    )
    zones = parser.add_argument_group("часовые пояса")
    zones.add_argument(
        "--tz",
        type=_zone,
        default=DEFAULT_TZ,
        help=f"пояс IANA в начале периода (по умолчанию {DEFAULT_TZ})",
    )
    zones.add_argument(
        "--tz-change",
        type=_tz_change,
        action="append",
        default=[],
        metavar="MOMENT=ZONE",
        help="с этого момента действует другой пояс, например 2026-10-05T12:00Z=America/New_York; "
        "можно повторять",
    )
    parser.add_argument("--out", default="-", help="файл NDJSON; '-' — stdout (по умолчанию)")
    return parser


def generate(config: Config) -> Iterator[str]:
    timeline = config.timeline()
    yield meta_line(config.devices)
    for day in config.days():
        yield from day_lines(plan_day(config.seed, day, timeline), config, timeline)


def _write(lines: Iterator[str], stream: TextIO) -> None:
    for line in lines:
        stream.write(line)
        stream.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    moments = [moment for moment, _zone in args.tz_change]
    if len(set(moments)) != len(moments):
        parser.error("два --tz-change в один и тот же момент")
    tz_changes = tuple(sorted(args.tz_change))
    today = Timeline(args.tz, tz_changes).local_date(datetime.now(UTC))
    try:
        first, last = resolve_period(args.start, args.end, args.days, today)
    except ValueError as error:
        parser.error(str(error))
    config = Config(
        first=first,
        last=last,
        seed=args.seed,
        devices=args.devices,
        hr_interval=args.hr_interval,
        unaligned=args.unaligned,
        tz=args.tz,
        tz_changes=tz_changes,
    )
    # LF and UTF-8 on every OS: the same seed gives byte-identical files on Windows and Linux.
    if args.out == "-":
        try:
            stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
            _write(generate(config), stdout)
            stdout.detach()
        except OSError as error:
            # Windows reports a closed pipe as EINVAL, POSIX as BrokenPipeError.
            if not isinstance(error, BrokenPipeError) and error.errno != errno.EINVAL:
                raise
            # The reader stopped early (htgen ... | head) - not an error. Send the rest of the
            # buffered output to devnull, so the final flush at exit does not fail again.
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    else:
        with open(args.out, "w", encoding="utf-8", newline="\n") as out:
            _write(generate(config), out)
    return 0
