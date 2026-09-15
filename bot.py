import logging
import os
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from schedule_parser import parse_schedule, dump_html
from lecture_joiner import run_today, now_ekb


# ---------- Переменные окружения ----------
load_dotenv()

LECTURE_LOGIN = os.getenv("LECTURE_LOGIN")
LECTURE_PASSWORD = os.getenv("LECTURE_PASSWORD")
LECTURE_URL = os.getenv("LECTURE_URL")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

if not all([LECTURE_LOGIN, LECTURE_PASSWORD, LECTURE_URL]):
    raise EnvironmentError("Не заданы LECTURE_LOGIN / LECTURE_PASSWORD / LECTURE_URL")


# ---------- Логирование ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------- Константы ----------
SCHEDULE_URL = "https://istudent.urfu.ru/s/schedule"


# ---------- Селекторы входа ----------
SELECTORS = {
    "login_link":     (By.CSS_SELECTOR, "a.auth"),
    "username_field": (By.ID, "username"),
    "password_field": (By.ID, "password"),
    "submit_button":  (By.ID, "kc-login"),
}


# ---------- Драйвер ----------
def create_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    return webdriver.Chrome(options=options)


# ---------- Вход ----------
def login(driver: webdriver.Chrome) -> None:
    wait = WebDriverWait(driver, 20)

    logger.info("Открываю %s", LECTURE_URL)
    driver.get(LECTURE_URL)

    logger.info("Кликаю 'Вход'")
    wait.until(EC.element_to_be_clickable(SELECTORS["login_link"])).click()

    logger.info("Жду форму Keycloak")
    username_field = wait.until(
        EC.presence_of_element_located(SELECTORS["username_field"])
    )

    username_field.send_keys(LECTURE_LOGIN)
    driver.find_element(*SELECTORS["password_field"]).send_keys(LECTURE_PASSWORD)
    driver.find_element(*SELECTORS["submit_button"]).click()

    logger.info("Жду завершения редиректа после логина")
    wait.until(EC.staleness_of(username_field))
    time.sleep(2)
    logger.info("Вход выполнен. URL: %s", driver.current_url)


# ---------- Переход на расписание ----------
def open_schedule(driver: webdriver.Chrome) -> None:
    logger.info("Перехожу на расписание: %s", SCHEDULE_URL)
    driver.get(SCHEDULE_URL)
    WebDriverWait(driver, 20).until(EC.url_contains("/s/schedule"))
    logger.info("Открыт URL: %s", driver.current_url)


# ---------- Main ----------
def main() -> None:
    logger.info("HEADLESS = %s", HEADLESS)
    logger.info("Время бота (Екатеринбург): %s", now_ekb().strftime("%Y-%m-%d %H:%M:%S %Z"))
    driver = create_driver(headless=HEADLESS)
    try:
        # 1. Логин
        login(driver)

        # 2. Переход на расписание
        open_schedule(driver)

        # 3. Парсинг расписания
        lessons = parse_schedule(driver)
        if not lessons:
            dump_html(driver)
            logger.warning("Расписание пустое — проверь селекторы, HTML в schedule.html")
            return

        logger.info("Всего пар в расписании: %d", len(lessons))
        for r in lessons:
            logger.info("  [%s] %s — %s — %s",
                        r["day"], r["time"], r["subject"], r["link"] or "(нет ссылки)")

        # 4. Подключение к сегодняшним парам по времени
        run_today(driver, lessons)

    except (TimeoutException, WebDriverException) as e:
        logger.error("Ошибка: %s", e)
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()