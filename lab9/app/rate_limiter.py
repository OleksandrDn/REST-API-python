import redis
import time
import asyncio
from typing import Optional
from fastapi import HTTPException, Request
from functools import wraps
import os
import logging

logger = logging.getLogger(__name__)

# Конфігурація Redis
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))

# Ліміти запитів
AUTHENTICATED_LIMIT = int(os.environ.get("AUTHENTICATED_LIMIT", "10"))  # 10 запитів за хвилину
ANONYMOUS_LIMIT = int(os.environ.get("ANONYMOUS_LIMIT", "2"))  # 2 запити за хвилину
WINDOW_SIZE = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))  # 60 секунд

class RateLimiter:
    def __init__(self, redis_client=None):
        """
        Ініціалізація rate limiter
        
        Args:
            redis_client: Опціональний Redis клієнт для тестування
        """
        if redis_client:
            self.redis_client = redis_client
        else:
            try:
                self.redis_client = redis.from_url(
                    REDIS_URL, 
                    db=REDIS_DB, 
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Перевіряємо з'єднання
                self.redis_client.ping()
                logger.info("Успішне підключення до Redis")
            except Exception as e:
                logger.error(f"Помилка підключення до Redis: {e}")
                # Fallback до in-memory словника для development
                self.redis_client = None
                self._memory_store = {}
                logger.warning("Використовується in-memory сховище замість Redis")

    def _get_client_identifier(self, request: Request, user_id: Optional[str] = None) -> str:
        """
        Отримує унікальний ідентифікатор клієнта
        
        Args:
            request: FastAPI request об'єкт
            user_id: ID авторизованого користувача (якщо є)
            
        Returns:
            str: Унікальний ідентифікатор клієнта
        """
        if user_id:
            return f"user:{user_id}"
        
        # Для анонімних користувачів використовуємо IP адресу
        client_ip = request.client.host if request.client else "unknown"
        
        # Перевіряємо заголовки для проксі
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            client_ip = real_ip
            
        return f"anon:{client_ip}"

    def _get_limit_for_user(self, user_id: Optional[str]) -> int:
        """
        Отримує ліміт запитів для користувача
        
        Args:
            user_id: ID користувача (None для анонімних)
            
        Returns:
            int: Ліміт запитів за хвилину
        """
        return AUTHENTICATED_LIMIT if user_id else ANONYMOUS_LIMIT

    async def _check_rate_limit_redis(self, identifier: str, limit: int) -> tuple[bool, int, int]:
        """
        Перевіряє rate limit використовуючи Redis
        
        Args:
            identifier: Унікальний ідентифікатор клієнта
            limit: Максимальна кількість запитів
            
        Returns:
            tuple: (allowed: bool, remaining: int, reset_time: int)
        """
        try:
            current_time = time.time()
            window_start = current_time - WINDOW_SIZE
            
            print(f"DEBUG: identifier={identifier}, limit={limit}, current_time={current_time}, window_start={window_start}")
            
            # Використовуємо Redis pipeline для атомарних операцій
            pipe = self.redis_client.pipeline()
            
            # Видаляємо старі записи (які старші за window_start)
            pipe.zremrangebyscore(identifier, 0, window_start)
            
            # Отримуємо кількість записів після очищення
            pipe.zcard(identifier)
            
            # Виконуємо операції
            results = pipe.execute()
            current_count = results[1]  # Результат zcard
            
            print(f"DEBUG: після очищення старих записів, current_count={current_count}")
            
            # Перевіряємо чи можемо додати новий запит
            if current_count < limit:
                # Дозволяємо запит - додаємо його до лічильника
                print(f"DEBUG: дозволяємо запит ({current_count} < {limit})")
                pipe = self.redis_client.pipeline()
                # Використовуємо current_time як score та як member для унікальності
                pipe.zadd(identifier, {f"req_{current_time}": current_time})
                pipe.expire(identifier, WINDOW_SIZE + 10)
                pipe.execute()
                
                allowed = True
                remaining = limit - current_count - 1  # -1 бо щойно додали запит
            else:
                # Блокуємо запит
                print(f"DEBUG: блокуємо запит ({current_count} >= {limit})")
                allowed = False
                remaining = 0
            
            reset_time = int(current_time) + WINDOW_SIZE
            print(f"DEBUG: результат - allowed={allowed}, remaining={remaining}")
            return allowed, remaining, reset_time
            
        except Exception as e:
            logger.error(f"Помилка при роботі з Redis: {e}")
            # У випадку помилки дозволяємо запит
            return True, limit, int(time.time()) + WINDOW_SIZE

    def _check_rate_limit_memory(self, identifier: str, limit: int) -> tuple[bool, int, int]:
        """
        Перевіряє rate limit використовуючи in-memory сховище
        
        Args:
            identifier: Унікальний ідентифікатор клієнта
            limit: Максимальна кількість запитів
            
        Returns:
            tuple: (allowed: bool, remaining: int, reset_time: int)
        """
        current_time = int(time.time())
        window_start = current_time - WINDOW_SIZE
        
        # Ініціалізуємо список для клієнта якщо його немає
        if identifier not in self._memory_store:
            self._memory_store[identifier] = []
        
        # Видаляємо старі записи
        self._memory_store[identifier] = [
            timestamp for timestamp in self._memory_store[identifier]
            if timestamp > window_start
        ]
        
        current_count = len(self._memory_store[identifier])
        
        # Перевіряємо чи можемо додати новий запит
        if current_count < limit:
            # Дозволяємо запит - додаємо його до лічільника
            self._memory_store[identifier].append(current_time)
            allowed = True
            remaining = limit - current_count - 1  # -1 бо щойно додали запит
        else:
            # Блокуємо запит
            allowed = False
            remaining = 0
        
        reset_time = current_time + WINDOW_SIZE
        return allowed, remaining, reset_time

    async def check_rate_limit(self, request: Request, user_id: Optional[str] = None) -> tuple[bool, int, int]:
        """
        Перевіряє rate limit для клієнта
        
        Args:
            request: FastAPI request об'єкт
            user_id: ID авторизованого користувача (якщо є)
            
        Returns:
            tuple: (allowed: bool, remaining: int, reset_time: int)
        """
        identifier = self._get_client_identifier(request, user_id)
        limit = self._get_limit_for_user(user_id)
        
        if self.redis_client:
            return await self._check_rate_limit_redis(identifier, limit)
        else:
            return self._check_rate_limit_memory(identifier, limit)

# Глобальний екземпляр rate limiter
rate_limiter = RateLimiter()

async def rate_limit_dependency(request: Request):
    """
    Dependency для перевірки rate limit анонімних користувачів
    """
    allowed, remaining, reset_time = await rate_limiter.check_rate_limit(request)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Перевищено ліміт запитів",
            headers={
                "X-RateLimit-Limit": str(ANONYMOUS_LIMIT),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(WINDOW_SIZE)
            }
        )
    
    # Додаємо заголовки до відповіді
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(ANONYMOUS_LIMIT),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time)
    }

async def authenticated_rate_limit_dependency(request: Request, current_user: dict):
    """
    Dependency для перевірки rate limit авторизованих користувачів
    """
    user_id = str(current_user["_id"])
    allowed, remaining, reset_time = await rate_limiter.check_rate_limit(request, user_id)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Перевищено ліміт запитів",
            headers={
                "X-RateLimit-Limit": str(AUTHENTICATED_LIMIT),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(WINDOW_SIZE)
            }
        )
    
    # Додаємо заголовки до відповіді
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(AUTHENTICATED_LIMIT),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time)
    }