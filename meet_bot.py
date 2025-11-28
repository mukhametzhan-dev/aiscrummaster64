# Fix for distutils compatibility with Python 3.12+
import distutils_fix

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
import logging
import datetime

# Конфигурация
BACKEND_API_URL = "http://localhost:8000" # Базовый URL
BOT_NAME = "AI Scrum Master"

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GoogleMeetBot:
    def __init__(self, headless=False):
        self.options = uc.ChromeOptions()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument("--disable-infobars")
        self.options.add_argument("--start-maximized")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage") # Часто нужно для Docker
        self.options.add_argument("--use-fake-ui-for-media-stream") 
        
        self.driver = uc.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, 20)
        self.seen_captions = set() # Для дедупликации: speaker---text

    def join_meeting(self, meeting_url):
        logging.info(f"Переход по ссылке: {meeting_url}")
        self.driver.get(meeting_url)
        # Здесь можно добавить логику входа (логин, клик "Join" и т.д.)
        time.sleep(5) 

    def turn_on_captions(self):
        logging.info("Попытка включить субтитры...")
        try:
            # Логика из content.js: ищем кнопку с aria-label, содержащим "turn on captions" или "تفعيل"
            # Используем XPath для поиска по частичному совпадению атрибута
            xpath = "//button[contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'turn on captions') or contains(@aria-label, 'تفعيل')]"
            
            button = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            button.click()
            logging.info("Кнопка субтитров нажата.")
            time.sleep(2)
        except Exception as e:
            logging.error(f"Не удалось включить субтитры через кнопку: {e}")
            # Фолбек на хоткей 'c'
            try:
                body = self.driver.find_element(By.TAG_NAME, 'body')
                body.send_keys('c')
                logging.info("Отправлена команда 'c'.")
            except Exception as e2:
                logging.error(f"Не удалось включить субтитры через хоткей: {e2}")

    def get_new_captions(self):
        """
        Сканирует DOM на наличие новых субтитров, используя логику из content.js.
        Возвращает список новых записей.
        """
        new_entries = []
        try:
            # Селекторы из content.js
            # .nMcdL - блок субтитра
            # .NWpY1d - спикер
            # .ygicle - текст
            
            blocks = self.driver.find_elements(By.CSS_SELECTOR, '.nMcdL')
            
            for block in blocks:
                try:
                    speaker_el = block.find_element(By.CSS_SELECTOR, '.NWpY1d')
                    text_el = block.find_element(By.CSS_SELECTOR, '.ygicle')
                    
                    speaker = speaker_el.text.strip()
                    text = text_el.text.strip()
                    
                    if not speaker or not text:
                        continue

                    # Ключ для дедупликации
                    key = f"{speaker}---{text}"
                    
                    if key not in self.seen_captions:
                        self.seen_captions.add(key)
                        
                        # Формат времени как в content.js: HH:MM:SS (en-GB)
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        
                        entry = {
                            "speaker": speaker,
                            "text": text,
                            "timestamp": timestamp
                        }
                        new_entries.append(entry)
                        logging.info(f"Captured: [{timestamp}] {speaker}: {text}")
                except Exception:
                    # Игнорируем ошибки внутри конкретного блока (например, элемент исчез)
                    continue
                    
        except Exception as e:
            logging.error(f"Ошибка при парсинге субтитров: {e}")
            
        return new_entries

    def send_chunk(self, chunk_data):
        if not chunk_data:
            return

        url = f"{BACKEND_API_URL}/api/transcript/chunk"
        payload = {
            "bot_name": BOT_NAME,
            "timestamp": time.time(),
            "chunk": chunk_data
        }
        
        try:
            logging.info(f"Отправка чанка ({len(chunk_data)} записей)...")
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            logging.info("Чанк успешно отправлен.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при отправке чанка: {e}")

    def send_final(self, full_transcript):
        if not full_transcript:
            logging.warning("Нет данных для финальной отправки.")
            return

        # Формат отправки как в background.js
        # transcript: fullText (строка), raw_data: list, meeting_date: ISO
        
        url = f"{BACKEND_API_URL}/api/meeting/transcript" # URL из background.js
        
        # Формируем полный текст как в background.js
        full_text_str = "\n".join([f"[{entry['timestamp']}] {entry['speaker']}: {entry['text']}" for entry in full_transcript])
        
        payload = {
            "transcript": full_text_str,
            "raw_data": full_transcript,
            "meeting_date": datetime.datetime.now().isoformat()
        }

        try:
            logging.info("Отправка финального транскрипта...")
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logging.info("Финальный транскрипт успешно отправлен.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при финальной отправке: {e}")

    def listen_loop(self):
        logging.info("Запуск цикла прослушивания...")
        start_time = time.time()
        chunk_buffer = [] 
        full_transcript = [] 

        try:
            while True:
                # 1. Парсинг
                new_items = self.get_new_captions()
                if new_items:
                    chunk_buffer.extend(new_items)
                    full_transcript.extend(new_items)

                # 2. Таймер 5 минут
                if time.time() - start_time > 300:
                    self.send_chunk(chunk_buffer)
                    chunk_buffer = [] 
                    start_time = time.time() 

                # 3. Проверка браузера
                try:
                    self.driver.title 
                except Exception:
                    logging.warning("Браузер недоступен. Завершение работы.")
                    break
                    
                time.sleep(1) 

        except KeyboardInterrupt:
            logging.info("Остановка бота пользователем...")
        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")
        finally:
            logging.info("Завершение работы, отправка данных...")
            self.send_final(full_transcript)
            try:
                self.driver.quit()
            except Exception:
                pass
            logging.info("Бот остановлен.")

if __name__ == "__main__":
    # Можно передавать аргументы через переменные окружения или argparse
    import os
    MEETING_URL = os.getenv("MEETING_URL", "https://meet.google.com/fgu-szza-qei")
    HEADLESS = os.getenv("HEADLESS", "False").lower() == "true"
    
    bot = GoogleMeetBot(headless=HEADLESS)
    try:
        bot.join_meeting(MEETING_URL)
        # В Docker скорее всего придется делать авто-логин или использовать профиль
        # Для локального теста даем время
        if not HEADLESS:
             input("Нажмите Enter после входа во встречу...")
        else:
             time.sleep(10) # Ждем загрузки в headless (тут нужна доп. логика входа)
             
        bot.turn_on_captions()
        bot.listen_loop()
    except Exception as e:
        logging.error(f"Ошибка запуска: {e}")
        bot.driver.quit()
