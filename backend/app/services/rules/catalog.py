"""R1–R6 as the user sees them (SPEC F9): title, description, thresholds, order on the page.

The thresholds live in code (the rule modules) and are copied to `rules.params` by the migration
that seeds the table (0010); a test keeps the two equal. Users do not edit them.
"""

from dataclasses import dataclass
from typing import Any

from app.services.rules import r1, r2, r3, r4, r5, r6


@dataclass(frozen=True)
class RuleInfo:
    code: str
    title: str
    description: str
    params: dict[str, Any]
    sort_order: int


CATALOG: tuple[RuleInfo, ...] = (
    RuleInfo(
        "R1",
        "Недосып",
        "Три валидные ночи подряд, в каждой меньше 6 ч сна. Закрывается сама после валидной ночи"
        " с 7 ч сна и больше.",
        r1.PARAMS,
        1,
    ),
    RuleInfo(
        "R2",
        "Мало шагов",
        "Три полных дня подряд, в каждый меньше половины цели по шагам. Закрывается сама после"
        " полного дня с выполненной целью.",
        r2.PARAMS,
        2,
    ),
    RuleInfo(
        "R3",
        "Повышенный пульс в покое",
        "Два дня подряд пульс в покое на 7 уд/мин и больше выше базы — среднего за 14 дней до них"
        " (нужно не меньше 7 значений). Закрывается сама, когда пульс в покое ниже базы + 4.",
        r3.PARAMS,
        3,
    ),
    RuleInfo(
        "R4",
        "Сон хуже, чем на прошлой неделе",
        "Средний сон за прошлую неделю меньше, чем за позапрошлую, на 60 мин и больше (в каждой"
        " неделе не меньше 5 валидных ночей). Закрывается сама, когда разница меньше 30 мин.",
        r4.PARAMS,
        4,
    ),
    RuleInfo(
        "R5",
        "Нерегулярный отбой",
        "Стандартное отклонение времени отбоя за последние 7 ночей больше 90 мин (нужно не меньше"
        " 5 валидных ночей из 7). Закрывается сама, когда оно меньше 60 мин.",
        r5.PARAMS,
        5,
    ),
    RuleInfo(
        "R6",
        "Нет активности",
        "Пять полных дней подряд, в каждый меньше 15 активных минут. Закрывается сама после"
        " полного дня с 15 активными минутами и больше.",
        r6.PARAMS,
        6,
    ),
)
