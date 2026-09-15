"""
Управление: прогон пар на сегодня, диспетчеризация в нужный жойнер.

Только оркестрация + время + выход. Логика входа — в bbb_joiner / moodle_joiner.
"""

import logging
from datetime import timedelta

from time_utils import (
    now_ekb,
    wait_until,
    parse_date,
    parse_time_today,
)
from bbb_joiner import join_bbb
from moodle_joiner import join_moodle

logger = logging.getLogger(__name__)


# Re-export для bot.py (from lecture_joiner import now_ekb)
__all__ = ["run_today", "now_ekb"]


# ============================================================
#  НАСТРОЙКИ
# ============================================================
JOIN_BEFORE_MINUTES = 2
LECTURE_DURATION_MIN = 90


# ============================================================
#  ГЛАВНАЯ ФУНКЦИЯ
# ============================================================
def run_today(driver, lessons: list[dict]) -> None:
    logger.info("Время бота (Екатеринбург): %s",
                now_ekb().strftime("%Y-%m-%d %H:%M:%S %Z"))

    today = _today_lessons(lessons)
    if not today:
        logger.info("На сегодня пар нет")
        return

    logger.info("Пар на сегодня: %d", len(today))
    for lesson in today:
        _handle_lesson(driver, lesson)


# ============================================================
#  ФИЛЬТР ПО ДАТЕ
# ============================================================
def _today_lessons(lessons: list[dict]) -> list[dict]:
    today = now_ekb().date()
    result = []
    for lesson in lessons:
        lesson_date = parse_date(lesson.get("day", ""))
        if lesson_date and lesson_date == today:
            result.append(lesson)
    result.sort(key=lambda x: x.get("time", ""))
    return result


# ============================================================
#  ОБРАБОТКА ОДНОЙ ПАРЫ
# ============================================================
def _handle_lesson(driver, lesson: dict) -> None:
    subject = lesson.get("subject", "?")
    time_str = lesson.get("time", "")
    link = lesson.get("link", "")

    if not link:
        logger.info("Пропускаю '%s' (%s) — нет ссылки", subject, time_str)
        return

    start = parse_time_today(time_str)
    if start is None:
        logger.warning("Не понял время '%s' у пары '%s'", time_str, subject)
        return

    end_time = start + timedelta(minutes=LECTURE_DURATION_MIN)
    join_at = start - timedelta(minutes=JOIN_BEFORE_MINUTES)
    now = now_ekb()

    logger.info("Пара '%s': начало %s, конец %s, подключаюсь в %s (Екб)",
                subject,
                start.strftime("%H:%M"),
                end_time.strftime("%H:%M"),
                join_at.strftime("%H:%M"))

    if now > end_time:
        logger.info("Пара '%s' уже прошла (сейчас %s > %s)",
                    subject, now.strftime("%H:%M"), end_time.strftime("%H:%M"))
        return

    if now < join_at:
        logger.info("Жду до %s (сейчас %s)",
                    join_at.strftime("%H:%M"), now.strftime("%H:%M"))
        wait_until(join_at)

    # Подключаемся
    logger.info("Подключаюсь к '%s'", subject)
    joined = False
    try:
        joined = _dispatch_join(driver, link)
    except Exception as e:
        logger.error("Исключение при подключении к '%s': %s", subject, e)

    if not joined:
        logger.warning("Комната '%s' не открыта — пропускаю пару", subject)
        return

    logger.info("✅ Подключение к '%s' выполнено", subject)
    logger.info("Сижу до %s", end_time.strftime("%H:%M"))
    wait_until(end_time)

    logger.info("Время пары '%s' истекло (сейчас %s)",
                subject, now_ekb().strftime("%H:%M"))
    _leave_lecture(driver)


# ============================================================
#  ДИСПЕТЧЕР
# ============================================================
def _dispatch_join(driver, url: str) -> bool:
    """Выбирает нужный жойнер по URL и возвращает результат."""
    if "elearn.urfu.ru/mod/bigbluebuttonbn" in url:
        return join_moodle(driver, url)
    if "bbb.urfu.ru" in url:
        return join_bbb(driver, url)

    logger.warning("Неизвестный тип ссылки: %s", url)
    return False


# ============================================================
#  ВЫХОД
# ============================================================
def _leave_lecture(driver) -> None:
    _close_tab(driver)


def _close_tab(driver) -> None:
    try:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[-1])
            logger.info("Вкладка лекции закрыта")
        else:
            logger.info("Последняя вкладка — оставляю открытой")
    except Exception as e:
        logger.warning("Не удалось закрыть вкладку: %s", e)