"""
Ручной тест подключения к лекциям.

Запуск:
    python test_joiner.py

Что делает:
    1. Логинится на istudent.urfu.ru
    2. Открывает расписание и парсит все пары
    3. Печатает список с номерами
    4. Просит ввести номер пары
    5. Принудительно подключается по выбранной ссылке
       (без проверки времени — даже если пара прошла или не началась)
    6. Держит браузер открытым до Enter
"""

import logging
import os
import sys
import time

from dotenv import load_dotenv
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Импортируем логику из наших модулей
from bot import create_driver, login, open_schedule, SELECTORS
from schedule_parser import parse_schedule, dump_html
from lecture_joiner import _join_lecture, _leave_lecture


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    load_dotenv()
    headless = os.getenv("HEADLESS", "false").lower() == "true"

    driver = create_driver(headless=headless)
    try:
        # 1. Логин + расписание
        login(driver)
        open_schedule(driver)

        # 2. Парсинг
        lessons = parse_schedule(driver)
        if not lessons:
            dump_html(driver)
            print("\n⚠️  Парсер вернул 0 пар. HTML сохранён в schedule.html")
            return

        # 3. Печатаем список
        print("\n" + "=" * 80)
        print(f"  НАЙДЕНО ПАР: {len(lessons)}")
        print("=" * 80)
        for i, r in enumerate(lessons, start=1):
            link_short = (r["link"][:60] + "...") if len(r["link"]) > 60 else r["link"]
            print(f"  {i:>3}. [{r['day']}] {r['time']:<7} {r['subject'][:40]:<40}")
            print(f"       {link_short or '(нет ссылки)'}")
        print("=" * 80)

        # 4. Спрашиваем номер
        raw = input("\nВведи номер пары для принудительного подключения (или Enter для выхода): ").strip()
        if not raw:
            print("Выход.")
            return

        try:
            idx = int(raw)
        except ValueError:
            print(f"❌ '{raw}' — не число")
            return

        if not (1 <= idx <= len(lessons)):
            print(f"❌ Номер должен быть от 1 до {len(lessons)}")
            return

        lesson = lessons[idx - 1]
        print(f"\n→ Выбрана пара: [{lesson['day']}] {lesson['time']} — {lesson['subject']}")
        print(f"→ Ссылка: {lesson['link']}")

        if not lesson["link"]:
            print("❌ У этой пары нет ссылки — подключаться некуда")
            return

        # 5. Принудительно подключаемся (без проверки времени!)
        print("\n→ Принудительное подключение (игнорирую время)...")
        try:
            _join_lecture(driver, lesson["link"])
            print("✅ Подключение выполнено")
        except Exception as e:
            logger.error("Ошибка подключения: %s", e)

        # 6. Ждём Enter, чтобы держать браузер открытым
        input("\nНажми Enter, чтобы выйти из лекции и закрыть браузер...")
        _leave_lecture(driver)

    except (TimeoutException, WebDriverException) as e:
        logger.error("Ошибка: %s", e)
        # Даём посмотреть, что на экране
        input("\nНажми Enter, чтобы закрыть браузер...")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()