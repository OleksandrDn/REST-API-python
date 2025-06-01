from fastapi import Request, HTTPException, status, Depends
from typing import Dict, Any
import time
import asyncio
from collections import defaultdict

# Словники для зберігання інформації про rate limiting
# В продакшені краще використовувати Redis
rate_limit_storage: Dict[str, Dict[str, Any]] = defaultdict(dict)

# Налаштування rate limiting
RATE_LIMIT_REQUESTS = 100  # кількість запитів
RATE_LIMIT_WINDOW = 60     # вікно в секундах (1 хвилина)

AUTH_RATE_LIMIT_REQUESTS = 200  # для авторизованих користувачів
AUTH_RATE_LIMIT_WINDOW = 60     # вікно в секундах

async def get_client_ip(request: Request) -> str:
    """Отримує IP адресу клієнта"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

async def check_rate_limit(
    client_id: str, 
    max_requests: int, 
    window_seconds: int,
    request: Request
) -> bool:
    """
    Перевіряє rate limit для клієнта
    Повертає True якщо запит дозволений, False якщо перевищено ліміт
    """
    current_time = time.time()
    
    if client_id not in rate_limit_storage:
        rate_limit_storage[client_id] = {
            "requests": [],
            "window_start": current_time
        }
    
    client_data = rate_limit_storage[client_id]
    
    # Очищуємо старі запити поза вікном
    client_data["requests"] = [
        req_time for req_time in client_data["requests"]
        if current_time - req_time < window_seconds
    ]
    
    # Перевіряємо ліміт
    if len(client_data["requests"]) >= max_requests:
        # Додаємо заголовки rate limit
        remaining = 0
        reset_time = int(client_data["requests"][0] + window_seconds)
        retry_after = reset_time - int(current_time)
        
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
            "Retry-After": str(max(retry_after, 1))
        }
        
        return False
    
    # Додаємо поточний запит
    client_data["requests"].append(current_time)
    
    # Додаємо заголовки rate limit
    remaining = max_requests - len(client_data["requests"])
    reset_time = int(current_time + window_seconds)
    
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(max_requests),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time)
    }
    
    return True

async def rate_limit_dependency(request: Request):
    """
    Rate limiting для неавторизованих користувачів
    """
    client_ip = await get_client_ip(request)
    
    allowed = await check_rate_limit(
        client_id=f"ip:{client_ip}",
        max_requests=RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW,
        request=request
    )
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Перевищено ліміт запитів. Спробуйте пізніше."
        )

async def authenticated_rate_limit_dependency(request: Request, current_user: dict = None):
    """
    Rate limiting для авторизованих користувачів
    """
    if current_user is None:
        # Якщо користувач не передано, використовуємо IP
        client_ip = await get_client_ip(request)
        client_id = f"ip:{client_ip}"
    else:
        # Використовуємо ID користувача
        client_id = f"user:{current_user['_id']}"
    
    allowed = await check_rate_limit(
        client_id=client_id,
        max_requests=AUTH_RATE_LIMIT_REQUESTS,
        window_seconds=AUTH_RATE_LIMIT_WINDOW,
        request=request
    )
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Перевищено ліміт запитів. Спробуйте пізніше."
        )

# Функція-wrapper для використання в Depends
async def get_authenticated_rate_limit(
    request: Request,
    current_user: dict = Depends(lambda: None)  # Це буде замінено в routes
):
    """
    Wrapper функція для authenticated_rate_limit_dependency
    """
    return await authenticated_rate_limit_dependency(request, current_user)