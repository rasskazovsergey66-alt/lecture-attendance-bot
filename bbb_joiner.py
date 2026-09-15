"""
Подключение к прямой комнате bbb.urfu.ru.

Здесь же — общие Selenium-хелперы, которые использует и Moodle-жойнер:
  - wait_for_bbb_room()   — ждём появления /html5client/
  - switch_to_bbb_tab()   — переключение на новую вкладку BBB
  - dump_failure()        — сохранение скриншота/HTML при провале
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)


# ============================================================
#  НАСТРОЙКИ
# ============================================================
JOIN_MAX_ATTEMPTS = 3
JOIN_ROOM_TIMEOUT = 30     # сек, сколько ждать /html5client/
JOIN_RETRY_PAUSE = 5       # сек, пауза между попытками


# ============================================================
#  ПУБЛИЧНАЯ ФУНКЦИЯ
# ============================================================
def join_bbb(driver, url: str) -> bool:
    """
    Прямая комната bbb.urfu.ru: имя + галочка согласия + 'Присоединиться'.
    Возвращает True, если реально попали в /html5client/.
    """
    logger.info("bbb-joiner: открываю %s", url)

    for attempt in range(1, JOIN_MAX_ATTEMPTS + 1):
        logger.info("Попытка подключения %d/%d", attempt, JOIN_MAX_ATTEMPTS)

        driver.get(url)
        time.sleep(4)
        logger.info("URL после открытия: %s", driver.current_url)

        # Если bbb выкинул обратно на istudent — комната ещё не открыта
        if "bbb.urfu.ru" not in driver.current_url:
            logger.warning("bbb.urfu.ru выкинул на %s — возможно, комната ещё не открыта",
                           driver.current_url)
            time.sleep(JOIN_RETRY_PAUSE)
            continue

        _fill_join_form(driver)
        logger.info("URL после клика 'Присоединиться': %s", driver.current_url)

        if wait_for_bbb_room(driver, timeout=JOIN_ROOM_TIMEOUT):
            return True

        dump_failure(driver, attempt)
        logger.warning("Попытка %d не удалась. URL: %s", attempt, driver.current_url)

        if attempt < JOIN_MAX_ATTEMPTS:
            time.sleep(JOIN_RETRY_PAUSE)

    logger.error("bbb-joiner: не удалось зайти после %d попыток", JOIN_MAX_ATTEMPTS)
    return False


# ============================================================
#  ЗАПОЛНЕНИЕ ФОРМЫ
# ============================================================
def _fill_join_form(driver) -> None:
    """Имя + галочка согласия + кнопка 'Присоединиться'."""
    wait = WebDriverWait(driver, 30)

    # 1. Имя
    name_selector = (By.CSS_SELECTOR, "input#joinFormName.form-control")
    try:
        name_input = wait.until(EC.presence_of_element_located(name_selector))
        name_input.clear()
        name_input.send_keys("Рассказов Сергей")
        logger.info("Ввёл имя в joinFormName")
    except TimeoutException:
        logger.warning("Поле joinFormName не найдено")
        return

    # 2. Галочка согласия — БЕЗ НЕЁ КНОПКА НЕ СРАБАТЫВАЕТ
    consent_selector = (By.CSS_SELECTOR, "input#consentCheck.form-check-input")
    try:
        consent = wait.until(EC.presence_of_element_located(consent_selector))
        if not consent.is_selected():
            driver.execute_script("arguments[0].click();", consent)
            time.sleep(0.3)

        if consent.is_selected():
            logger.info("✅ Галочка согласия установлена")
        else:
            logger.warning("⚠️ Галочка согласия НЕ установилась")
    except TimeoutException:
        logger.warning("Чекбокс consentCheck не найден")
        return

    # 3. Кнопка
    join_btn_selector = (By.CSS_SELECTOR,
                         "button.mt-3.d-block.float-end.btn.btn-brand")
    try:
        join_btn = wait.until(EC.element_to_be_clickable(join_btn_selector))
        logger.info("Кликаю 'Присоединиться'")
        try:
            join_btn.click()
        except Exception as e:
            logger.warning("Обычный клик упал (%s), JS-клик", e)
            driver.execute_script("arguments[0].click();", join_btn)
        time.sleep(3)
    except TimeoutException:
        logger.warning("Кнопка 'Присоединиться' не найдена")


# ============================================================
#  ОБЩИЕ ХЕЛПЕРЫ
# ============================================================
from selenium.webdriver.support import expected_conditions as EC


def switch_to_bbb_tab(driver, timeout: int = 30) -> bool:
    """
    Ждёт появления новой вкладки через EC.new_window_is_opened
    и переключается на неё. Возвращает True, если переключились.
    """
    initial_handles = driver.window_handles

    try:
        WebDriverWait(driver, timeout).until(
            EC.new_window_is_opened(initial_handles)
        )
    except TimeoutException:
        logger.warning("Новая вкладка не появилась за %d сек. Окон: %d",
                       timeout, len(driver.window_handles))
        return False

    new_handles = [h for h in driver.window_handles if h not in initial_handles]
    if not new_handles:
        logger.warning("EC сработал, но новых handles нет. Текущие: %s",
                       driver.window_handles)
        return False

    driver.switch_to.window(new_handles[-1])
    logger.info("Переключился на новую вкладку: %s", driver.current_url)
    return True


def wait_for_bbb_room(driver, timeout: int = 30) -> bool:
    """
    Ждёт /html5client/ либо в текущей вкладке, либо в новой.
    Возвращает True, если комната открыта.
    """
    # Случай 1: уже в комнате в текущей вкладке
    if "/html5client/" in driver.current_url:
        logger.info("✅ Уже в комнате: %s", driver.current_url)
        return True

    # Случай 2: комната открылась в новой вкладке
    if switch_to_bbb_tab(driver, timeout=timeout):
        # После переключения может быть короткий редирект
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: "/html5client/" in d.current_url
            )
            logger.info("✅ Комната открыта: %s", driver.current_url)
            return True
        except TimeoutException:
            logger.warning("Новая вкладка есть, но /html5client/ не появился: %s",
                           driver.current_url)
            return False

    logger.warning("❌ Ни перехода, ни новой вкладки. URL: %s", driver.current_url)
    return False


def dump_failure(driver, attempt: int) -> None:
    """Сохраняет скриншот и HTML при провале."""
    try:
        png = f"fail_attempt{attempt}.png"
        html = f"fail_attempt{attempt}.html"
        driver.save_screenshot(png)
        with open(html, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Диагностика сохранена: %s, %s", png, html)
    except Exception as e:
        logger.debug("Не удалось сохранить диагностику: %s", e)