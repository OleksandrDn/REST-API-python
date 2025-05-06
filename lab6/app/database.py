from pymongo import MongoClient
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://mongo:27017")
MAX_CONN_RETRIES = int(os.environ.get("MAX_CONN_RETRIES", "5"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "5"))

client = None
db = None

def initialize_db():
    global client, db
    retry_count = 0

    while retry_count < MAX_CONN_RETRIES:
        try:
            logger.info(f"Спроба підключення до MongoDB ({retry_count + 1}/{MAX_CONN_RETRIES})")
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')  # перевірка з'єднання
            db = client["library"]
            logger.info("MongoDB з'єднання встановлено успішно!")
            return db  # Повертаємо db, щоб інші частини програми могли з ним працювати
        except Exception as e:
            retry_count += 1
            logger.error(f"Помилка підключення до MongoDB: {e}")
            if retry_count < MAX_CONN_RETRIES:
                logger.info(f"Повторна спроба через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Не вдалося підключитися до MongoDB")
                return None  # Якщо не вдалося підключитися, повертаємо None

# Для сумісності з main.py
def connect_to_mongo():
    return initialize_db()

# Аліас для сумісності з існуючим кодом
connect_to_mongo = initialize_db