"""
Парсер расписания с istudent.urfu.ru.
Работает с УЖЕ открытой страницей /s/schedule. Навигацию делает bot.py.
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


logger = logging.getLogger(__name__)


# ============================================================
#  СЕЛЕКТОРЫ РАСПИСАНИЯ (по DevTools УрФУ)
# ============================================================
SCHEDULE_SELECTORS = {
    "lesson_row": (By.XPATH, "//tr[.//td[contains(@class,'time')]]"),
    "time":       (By.CSS_SELECTOR, "td.time"),
    "subject":    (By.CSS_SELECTOR, "strong"),
    "link":       (By.CSS_SELECTOR,
                   "a[href*='bbb.urfu.ru'], a[href*='elearn.urfu.ru/mod/bigbluebuttonbn']"),
}


# ============================================================
#  ПАРСИНГ ТЕКУЩЕЙ СТРАНИЦЫ
# ============================================================
def parse_schedule(driver) -> list[dict]:
    """
    Парсит расписание с ТЕКУЩЕЙ открытой страницы.
    bot.py уже должен был сделать driver.get(SCHEDULE_URL).

    Возвращает список словарей:
        [{"day": "14 сентября 2026 г.", "time": "09:00",
          "subject": "Математический анализ",
          "link": "https://bbb.urfu.ru/rooms/..."}, ...]
    """
    logger.info("Парсю расписание. URL: %s", driver.current_url)

    # Ждём хотя бы одну строку с td.time
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(SCHEDULE_SELECTORS["lesson_row"])
        )
    except TimeoutException:
        logger.warning("Строки расписания не найдены — селектор неверный?")
        return []

    time.sleep(1)  # мелкая пауза на дорисовку

    rows: list[dict] = []
    lesson_rows = driver.find_elements(*SCHEDULE_SELECTORS["lesson_row"])
    logger.info("Найдено строк с парами: %d", len(lesson_rows))

    for tr in lesson_rows:
        # Дата — ближайший предыдущий div с id="schedule-event-date-..."
        day = _preceding_date(tr)

        time_str = _safe_text(tr, SCHEDULE_SELECTORS["time"])
        subject  = _safe_text(tr, SCHEDULE_SELECTORS["subject"])
        link     = _safe_attr(tr, SCHEDULE_SELECTORS["link"], "href")

        rows.append({
            "day":     day,
            "subject": subject,
            "time":    time_str,
            "link":    link,
        })

    logger.info("Всего распарсено пар: %d", len(rows))
    return rows


# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ
# ============================================================
def _preceding_date(tr) -> str:
    """Находит ближайший ПРЕДЫДУЩИЙ div с id, начинающимся на schedule-event-date-."""
    try:
        date_el = tr.find_element(
            By.XPATH,
            "preceding::div[starts-with(@id,'schedule-event-date-')][1]"
        )
        return date_el.text.strip()
    except Exception:
        return ""


def _safe_text(parent, selector) -> str:
    try:
        return parent.find_element(*selector).text.strip()
    except Exception:
        return ""


def _safe_attr(parent, selector, attr: str) -> str:
    try:
        return parent.find_element(*selector).get_attribute(attr) or ""
    except Exception:
        return ""


def dump_html(driver, path: str = "schedule.html") -> None:
    """Сохраняет HTML текущей страницы для анализа."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    logger.info("HTML сохранён: %s", path)