# lecture_joiner.py
"""
Подключение к лекциям с РЕАЛЬНОЙ проверкой времени по Екатеринбургу (UTC+5).

Часовой пояс жёстко зашит через zoneinfo — не зависит от TZ машины,
системных настроек GitHub runner'а и локального окружения.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)


# ============================================================
#  НАСТРОЙКИ
# ============================================================
JOIN_BEFORE_MINUTES = 2      # подключаться за N минут до начала
LECTURE_DURATION_MIN = 90    # длительность пары в минутах
CHECK_INTERVAL_SEC = 30      # как часто сверяться с часами

# Часовой пояс Екатеринбурга (UTC+5) — жёстко, независимо от машины
EKATERINBURG_TZ = ZoneInfo("Asia/Yekaterinburg")

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def now_ekb() -> datetime:
    """Текущее время в Екатеринбурге, независимо от TZ машины."""
    return datetime.now(EKATERINBURG_TZ)


# ============================================================
#  ГЛАВНАЯ ФУНКЦИЯ
# ============================================================
def run_today(driver, lessons: list[dict]) -> None:
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
        lesson_date = _parse_date(lesson.get("day", ""))
        if lesson_date and lesson_date == today:
            result.append(lesson)
    result.sort(key=lambda x: x.get("time", ""))
    return result


def _parse_date(day_str: str):
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

    start = _parse_time_today(time_str)
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
        _wait_until(join_at)

    logger.info("Подключаюсь к '%s'", subject)
    try:
        _join_lecture(driver, link)
        logger.info("Подключение к '%s' выполнено", subject)
    except Exception as e:
        logger.error("Не удалось подключиться к '%s': %s", subject, e)
        return

    logger.info("Сижу до %s (проверка каждые %d сек)",
                end_time.strftime("%H:%M"), CHECK_INTERVAL_SEC)
    _wait_until(end_time)

    logger.info("Время пары '%s' истекло (сейчас %s)",
                subject, now_ekb().strftime("%H:%M"))
    _leave_lecture(driver)


# ============================================================
#  ВХОД В КОМНАТУ
# ============================================================
def _join_lecture(driver, url: str) -> None:
    logger.info("Открываю: %s", url)
    driver.get(url)
    time.sleep(3)

    if "elearn.urfu.ru/mod/bigbluebuttonbn" in url:
        _click_moodle_join(driver)
    elif "bbb.urfu.ru" in url:
        _click_bbb_join(driver)
    else:
        logger.warning("Неизвестный тип ссылки: %s", url)
        return

    time.sleep(5)
    logger.info("Комната должна быть открыта")


def _click_moodle_join(driver) -> None:
    wait = WebDriverWait(driver, 20)
    selector = (By.CSS_SELECTOR, "a.btn.btn-primary.bbb-btn-action.m-1")
    try:
        btn = wait.until(EC.element_to_be_clickable(selector))
        logger.info("Кликаю 'Подключиться к сеансу' (Moodle)")
        btn.click()
        time.sleep(3)
    except TimeoutException:
        logger.warning("Кнопка 'Подключиться к сеансу' не найдена")


def _click_bbb_join(driver) -> None:
    wait = WebDriverWait(driver, 20)

    name_selector = (By.CSS_SELECTOR, "input#joinFormName.form-control")
    try:
        name_input = wait.until(EC.presence_of_element_located(name_selector))
        name_input.clear()
        name_input.send_keys("Рассказов Сергей")
        logger.info("Ввёл имя в поле joinFormName")
    except TimeoutException:
        logger.warning("Поле ввода имени (joinFormName) не найдено")
        return

    join_btn_selector = (By.CSS_SELECTOR, "button.mt-3.d-block.float-end.btn.btn-brand")
    try:
        join_btn = wait.until(EC.element_to_be_clickable(join_btn_selector))
        logger.info("Кликаю 'Присоединиться' (bbb.urfu.ru)")
        join_btn.click()
        time.sleep(3)
    except TimeoutException:
        logger.warning("Кнопка 'Присоединиться' не найдена")


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


# ============================================================
#  ВРЕМЯ: парсинг и ожидание
# ============================================================
def _parse_time_today(time_str: str):
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


def _wait_until(target: datetime) -> None:
    """
    Спит до target, но не слепым time.sleep.
    Каждые CHECK_INTERVAL_SEC секунд сверяется с now_ekb().
    """
    while True:
        now = now_ekb()
        delta = (target - now).total_seconds()

        if delta <= 0:
            logger.debug("_wait_until: цель %s достигнута (сейчас %s)",
                         target.strftime("%H:%M:%S"), now.strftime("%H:%M:%S"))
            return

        sleep_for = min(delta, CHECK_INTERVAL_SEC)
        logger.debug("_wait_until: до %s осталось %.0f сек, сплю %.0f",
                     target.strftime("%H:%M:%S"), delta, sleep_for)
        time.sleep(sleep_for)