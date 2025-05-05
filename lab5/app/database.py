from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
import asyncio
import logging
from app.models import Book

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Отримання URI для MongoDB з змінної оточення або використання значення за замовчуванням
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://mongo:27017")
MAX_CONN_RETRIES = int(os.environ.get("MAX_CONN_RETRIES", "5"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "5"))  # seconds

client = None

async def initialize_db():
    global client
    
    retry_count = 0
    while retry_count < MAX_CONN_RETRIES:
        try:
            logger.info(f"Спроба підключення до MongoDB ({retry_count+1}/{MAX_CONN_RETRIES})")
            client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            
            # Перевірка підключення
            await client.admin.command('ping')
            
            # Ініціалізація Beanie з моделями
            await init_beanie(
                database=client.library,
                document_models=[Book]
            )
            
            logger.info("MongoDB з'єднання встановлено успішно!")
            return True
        except Exception as e:
            retry_count += 1
            logger.error(f"Помилка підключення до MongoDB: {e}")
            
            if retry_count < MAX_CONN_RETRIES:
                logger.info(f"Повторна спроба через {RETRY_DELAY} секунд...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Не вдалося підключитися до MongoDB після {MAX_CONN_RETRIES} спроб")
                return False

# Функція перевірки з'єднання для використання в головному додатку
async def check_connection():
    if client is None:
        return await initialize_db()
    
    try:
        await client.admin.command('ping')
        return True
    except Exception as e:
        logger.error(f"Помилка перевірки підключення до MongoDB: {e}")
        return False
