# lecture_joiner.py (обновлённая версия)

import logging
import re
import time
from datetime import datetime, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

# ============================================================
#  НАСТРОЙКИ
# ============================================================
JOIN_BEFORE_MINUTES = 2      # подключаться за N минут до начала
LECTURE_DURATION_MIN = 90    # сколько минут сидеть на паре
CHECK_INTERVAL_SEC = 30      # как часто проверять «не пора ли»

# Русские месяцы → номер
MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# ============================================================
#  ГЛАВНАЯ ФУНКЦИЯ — прогоняет все пары на сегодня
# ============================================================
def run_today(driver, lessons: list[dict]) -> None:
    """Берёт все пары, фильтрует сегодняшние, ждёт нужного времени и подключается."""
    today = _today_lessons(lessons)
    if not today:
        logger.info("На сегодня пар нет")
        return

    logger.info("Пар на сегодня: %d", len(today))
    for lesson in today:
        _handle_lesson(driver, lesson)

# ============================================================
#  ФИЛЬТР ПО СЕГОДНЯШНЕЙ ДАТЕ
# ============================================================
def _today_lessons(lessons: list[dict]) -> list[dict]:
    """Оставляет только пары на сегодня и сортирует по времени."""
    today = datetime.now().date()
    result = []
    for lesson in lessons:
        lesson_date = _parse_date(lesson.get("day", ""))
        if lesson_date and lesson_date == today:
            result.append(lesson)
    result.sort(key=lambda x: x.get("time", ""))
    return result

def _parse_date(day_str: str):
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

    join_at = start - timedelta(minutes=JOIN_BEFORE_MINUTES)
    now = datetime.now()

    if now > start + timedelta(minutes=LECTURE_DURATION_MIN):
        logger.info("Пара '%s' (%s) уже прошла", subject, time_str)
        return

    if now < join_at:
        logger.info("Жду до %s для пары '%s' (%s)",
                    join_at.strftime("%H:%M"), subject, time_str)
        _wait_until(join_at)

    logger.info("Подключаюсь к '%s' (%s)", subject, time_str)
    try:
        _join_lecture(driver, link)
        logger.info("Подключение к '%s' выполнено", subject)
    except Exception as e:
        logger.error("Не удалось подключиться к '%s': %s", subject, e)
        return

    logger.info("Сижу на паре %d минут", LECTURE_DURATION_MIN)
    time.sleep(LECTURE_DURATION_MIN * 60)

    _leave_lecture(driver)

# ============================================================
#  ПОДКЛЮЧЕНИЕ К ЛЕКЦИИ (обновлено)
# ============================================================
def _join_lecture(driver, url: str) -> None:
    """
    Открывает ссылку и выполняет вход в зависимости от типа:
    - https://bbb.urfu.ru/rooms/... → ввод имени + клик "Присоединиться"
    - https://elearn.urfu.ru/mod/bigbluebuttonbn/... → клик "Подключиться к сеансу"
    После перехода в комнату — клик по "Только слушать".
    """
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

    # После входа в комнату — выбираем режим "Только слушать"
    _click_listen_only(driver)

def _click_moodle_join(driver) -> None:
    """Moodle: кнопка 'Подключиться к сеансу' (a.btn.btn-primary.bbb-btn-action)."""
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
    """
    Прямая комната bbb.urfu.ru: ввод имени в input#joinFormName
    и клик по button.mt-3.d-block.float-end.btn.btn-brand.
    """
    wait = WebDriverWait(driver, 20)

    # Ввод имени
    name_selector = (By.CSS_SELECTOR, "input#joinFormName.form-control")
    try:
        name_input = wait.until(EC.presence_of_element_located(name_selector))
        # Очищаем поле и вводим имя
        name_input.clear()
        # Используем имя, которое вы указали
        name_input.send_keys("Рассказов Сергей")
        logger.info("Ввёл имя в поле joinFormName")
    except TimeoutException:
        logger.warning("Поле ввода имени (joinFormName) не найдено")
        return

    # Клик по кнопке "Присоединиться"
    join_btn_selector = (By.CSS_SELECTOR, "button.mt-3.d-block.float-end.btn.btn-brand")
    try:
        join_btn = wait.until(EC.element_to_be_clickable(join_btn_selector))
        logger.info("Кликаю 'Присоединиться' (bbb.urfu.ru)")
        join_btn.click()
        time.sleep(3)
    except TimeoutException:
        logger.warning("Кнопка 'Присоединиться' не найдена")

def _click_listen_only(driver) -> None:
    """
    Клик по кнопке 'Только слушать' (иконка наушников).
    Используем JavaScript, так как элемент может быть в Shadow DOM
    или иметь сложную структуру (i.icon-bbb-listen).
    """
    wait = WebDriverWait(driver, 20)
    # Пробуем найти элемент по классу иконки. 
    # Если не сработает, попробуем найти по тексту "Только слушать".
    selectors = [
        (By.CSS_SELECTOR, "i.icon-bbb-listen"),
        (By.XPATH, "//i[contains(@class, 'icon-bbb-listen')]"),
        (By.XPATH, "//*[contains(text(), 'Только слушать')]"),
        (By.XPATH, "//*[contains(text(), 'Listen only')]"),
    ]
    
    for by, value in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((by, value)))
            # Кликаем через JavaScript, чтобы обойти проблемы с видимостью/Shadow DOM
            driver.execute_script("arguments[0].click();", el)
            logger.info("Кликнул 'Только слушать' (селектор: %s)", value)
            time.sleep(2)
            return
        except TimeoutException:
            continue
        except Exception as e:
            logger.debug("Ошибка при клике по '%s': %s", value, e)
            continue
            
    logger.warning("Кнопка 'Только слушать' не найдена")

def _leave_lecture(driver) -> None:
    """Пытается выйти из лекции (кнопка 'Покинуть')."""
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Покинуть') or contains(., 'Leave')]")
            )
        )
        btn.click()
        logger.info("Вышел из лекции")
    except TimeoutException:
        logger.info("Кнопка выхода не найдена — оставляю вкладку открытой")

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ
# ============================================================
def _parse_time_today(time_str: str):
    """'09:00' → datetime сегодня 09:00. None, если не распарсилось."""
    m = re.search(r"(\d{1,2}):(\d{2})", time_str or "")
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    now = datetime.now()
    try:
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    except ValueError:
        return None

def _wait_until(target: datetime) -> None:
    """Спит до target, просыпаясь каждые CHECK_INTERVAL_SEC для проверки."""
    while True:
        delta = (target - datetime.now()).total_seconds()
        if delta <= 0:
            return
        time.sleep(min(delta, CHECK_INTERVAL_SEC))