import os
import logging
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Змінні оточення з значеннями за замовчуванням
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://mongo:27017")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "library")
MAX_CONN_RETRIES = int(os.environ.get("MAX_CONN_RETRIES", "5"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "5"))

# Глобальні об'єкти для з'єднання з MongoDB
client = None
db = None

async def connect_to_mongo():
    """
    Підключення до MongoDB з повторними спробами.
    Викликається під час запуску FastAPI додатка.
    """
    global client, db
    
    for attempt in range(MAX_CONN_RETRIES):
        try:
            logger.info(f"Спроба підключення до MongoDB ({attempt + 1}/{MAX_CONN_RETRIES})")
            client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            
            # Перевірка підключення
            await client.admin.command('ping')
            
            # Отримання об'єкту бази даних
            db = client[DATABASE_NAME]
            
            logger.info(f"Успішне підключення до MongoDB (база даних: {DATABASE_NAME})")
            return db
        except Exception as e:
            logger.error(f"Помилка підключення: {e}")
            
            # Якщо це остання спроба, піднімаємо виняток
            if attempt == MAX_CONN_RETRIES - 1:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Не вдалося підключитися до MongoDB після {MAX_CONN_RETRIES} спроб"
                )
            
            # Чекаємо перед повторною спробою
            await asyncio.sleep(RETRY_DELAY)

async def close_mongo_connection():
    """
    Закриття з'єднання з MongoDB.
    Викликається під час завершення роботи FastAPI додатка.
    """
    global client
    if client:
        logger.info("Закриття з'єднання з MongoDB")
        client.close()

async def get_database():
    """
    Функція для отримання об'єкту бази даних.
    Використовується як залежність (dependency) у маршрутах.
    """
    global db
    if db is None:
        await connect_to_mongo()
    return db