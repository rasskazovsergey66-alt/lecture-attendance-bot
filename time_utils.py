"""
Время: часовой пояс Екатеринбурга, парсинг дат, ожидание.
Изолировано от логики подключения.
"""

import logging
import os
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


# ============================================================
#  НАСТРОЙКИ
# ============================================================
EKATERINBURG_TZ = ZoneInfo("Asia/Yekaterinburg")

# Локально можно поставить USE_EKB_TZ=false в .env,
# если Windows уже настроена на нужный пояс.
# В GitHub Actions (UTC) — оставляем true.
USE_EKB_TZ = os.getenv("USE_EKB_TZ", "true").lower() == "true"

CHECK_INTERVAL_SEC = 30   # как часто просыпаться и сверяться с часами

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


# ============================================================
#  ВРЕМЯ
# ============================================================
def now_ekb() -> datetime:
    """Текущее время в Екатеринбурге (или системное, если USE_EKB_TZ=false)."""
    if USE_EKB_TZ:
        return datetime.now(EKATERINBURG_TZ)
    return datetime.now()


def parse_date(day_str: str):
    """'14 сентября 2026 г.' → date(2026, 9, 14). None, если не распарсилось."""
    if not day_str:
        return None
    m = re.search(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", day_str.lower())
    if not m:
        return None
    day, month_name, year = m.groups()
    month = MONTHS_RU.get(month_name)
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day)).date()
    except ValueError:
        return None


def parse_time_today(time_str: str):
    """'09:00' или '09:00 - 10:30' → datetime Екб сегодня 09:00."""
    m = re.search(r"(\d{1,2}):(\d{2})", time_str or "")
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    now = now_ekb()
    try:
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    except ValueError:
        return None


def wait_until(target: datetime) -> None:
    """
    Спит до target, но не слепым time.sleep.
    Каждые CHECK_INTERVAL_SEC сек сверяется с now_ekb().
    """
    while True:
        now = now_ekb()
        delta = (target - now).total_seconds()

        if delta <= 0:
            logger.debug("wait_until: цель %s достигнута (сейчас %s)",
                         target.strftime("%H:%M:%S"), now.strftime("%H:%M:%S"))
            return

        sleep_for = min(delta, CHECK_INTERVAL_SEC)
        logger.debug("wait_until: до %s осталось %.0f сек, сплю %.0f",
                     target.strftime("%H:%M:%S"), delta, sleep_for)
        time.sleep(sleep_for)