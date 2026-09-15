"""
Подключение к сеансу BigBlueButton через Moodle (elearn.urfu.ru).
Использует общие хелперы из bbb_joiner.
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from bbb_joiner import (
    JOIN_MAX_ATTEMPTS,
    JOIN_ROOM_TIMEOUT,
    JOIN_RETRY_PAUSE,
    wait_for_bbb_room,
    dump_failure,
)

logger = logging.getLogger(__name__)


# ============================================================
#  ПУБЛИЧНАЯ ФУНКЦИЯ
# ============================================================
def join_moodle(driver, url: str) -> bool:
    """
    Moodle: клик 'Подключиться к сеансу'.
    Возвращает True, если реально попали в /html5client/.
    """
    logger.info("moodle-joiner: открываю %s", url)

    for attempt in range(1, JOIN_MAX_ATTEMPTS + 1):
        logger.info("Попытка подключения %d/%d", attempt, JOIN_MAX_ATTEMPTS)

        driver.get(url)
        time.sleep(4)
        logger.info("URL после открытия: %s", driver.current_url)

        clicked = _click_join_session(driver)
        if not clicked:
            logger.warning("Кнопка 'Подключиться к сеансу' не нажалась")
            dump_failure(driver, attempt)
            if attempt < JOIN_MAX_ATTEMPTS:
                time.sleep(JOIN_RETRY_PAUSE)
            continue

        logger.info("URL после клика: %s", driver.current_url)

        if wait_for_bbb_room(driver, timeout=JOIN_ROOM_TIMEOUT):
            return True

        dump_failure(driver, attempt)
        logger.warning("Попытка %d не удалась. URL: %s", attempt, driver.current_url)

        if attempt < JOIN_MAX_ATTEMPTS:
            time.sleep(JOIN_RETRY_PAUSE)

    logger.error("moodle-joiner: не удалось зайти после %d попыток", JOIN_MAX_ATTEMPTS)
    return False


# ============================================================
#  КЛИК ПО КНОПКЕ MOODLE
# ============================================================
def _click_join_session(driver) -> bool:
    """Moodle: 'Подключиться к сеансу' (a.btn.btn-primary.bbb-btn-action)."""
    wait = WebDriverWait(driver, 20)
    selector = (By.CSS_SELECTOR, "a.btn.btn-primary.bbb-btn-action.m-1")
    try:
        btn = wait.until(EC.element_to_be_clickable(selector))
        logger.info("Кликаю 'Подключиться к сеансу' (Moodle)")
        try:
            btn.click()
        except Exception as e:
            logger.warning("Обычный клик упал (%s), JS-клик", e)
            driver.execute_script("arguments[0].click();", btn)
        time.sleep(3)
        return True
    except TimeoutException:
        logger.warning("Кнопка 'Подключиться к сеансу' не найдена")
        return False