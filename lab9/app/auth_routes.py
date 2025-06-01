from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from bson import ObjectId
from datetime import datetime
from jose import JWTError, jwt

from app.database import get_database
from app.security import (
    UserCreate, UserLogin, UserResponse, Token,
    get_password_hash, verify_password, create_access_token, create_refresh_token,
    SECRET_KEY, ALGORITHM, oauth2_scheme
)
from app.rate_limiter import rate_limit_dependency, authenticated_rate_limit_dependency

router = APIRouter()

async def add_rate_limit_headers(request: Request, response: Response):
    """Додає заголовки rate limit до відповіді"""
    if hasattr(request.state, 'rate_limit_headers'):
        for key, value in request.state.rate_limit_headers.items():
            response.headers[key] = value

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    response: Response,
    user_data: UserCreate,
    db=Depends(get_database),
    _=Depends(rate_limit_dependency)  # Rate limiting для анонімних користувачів
):
    """
    Реєстрація нового користувача
    """
    # Перевіряємо, чи існує користувач з таким email
    existing_user = await db["users"].find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Користувач з таким email вже існує"
        )
    
    # Створюємо нового користувача
    now = datetime.utcnow()
    new_user = {
        "email": user_data.email,
        "username": user_data.username,
        "password": get_password_hash(user_data.password),
        "created_at": now,
        "updated_at": now
    }
    
    # Зберігаємо користувача в базі даних
    result = await db["users"].insert_one(new_user)
    
    # Отримуємо створеного користувача
    created_user = await db["users"].find_one({"_id": result.inserted_id})
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    # Формуємо відповідь
    return {
        "id": str(created_user["_id"]),
        "email": created_user["email"],
        "username": created_user["username"],
        "created_at": created_user["created_at"],
        "updated_at": created_user["updated_at"]
    }

@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_database),
    _=Depends(rate_limit_dependency)  # Rate limiting для анонімних користувачів
):
    """
    Отримання токена доступу через OAuth2 форму
    """
    # Знаходимо користувача за email
    user = await db["users"].find_one({"email": form_data.username})
    
    # Перевіряємо пароль
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний email або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Створюємо дані для токенів
    user_id = str(user["_id"])
    access_token_data = {"sub": user_id, "type": "access"}
    refresh_token_data = {"sub": user_id, "type": "refresh"}
    
    # Генеруємо токени
    access_token = create_access_token(access_token_data)
    refresh_token = create_refresh_token(refresh_token_data)
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=Token)
async def login_user(
    request: Request,
    response: Response,
    user_data: UserLogin,
    db=Depends(get_database),
    _=Depends(rate_limit_dependency)  # Rate limiting для анонімних користувачів
):
    """
    Вхід користувача через JSON
    """
    # Знаходимо користувача за email
    user = await db["users"].find_one({"email": user_data.email})
    
    # Перевіряємо пароль
    if not user or not verify_password(user_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний email або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Створюємо дані для токенів
    user_id = str(user["_id"])
    access_token_data = {"sub": user_id, "type": "access"}
    refresh_token_data = {"sub": user_id, "type": "refresh"}
    
    # Генеруємо токени
    access_token = create_access_token(access_token_data)
    refresh_token = create_refresh_token(refresh_token_data)
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    token: str = Depends(oauth2_scheme),
    db=Depends(get_database)
):
    """
    Оновлення токена доступу
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Невірний refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Декодуємо refresh token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        # Перевіряємо, чи це refresh token
        if user_id is None or token_type != "refresh":
            raise credentials_exception
            
        # Перевіряємо, чи існує користувач
        user = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            raise credentials_exception
        
        # Для refresh токена застосовуємо ліміт для авторизованих користувачів
        await authenticated_rate_limit_dependency(request, user)
            
        # Створюємо нові токени
        access_token_data = {"sub": user_id, "type": "access"}
        refresh_token_data = {"sub": user_id, "type": "refresh"}
        
        access_token = create_access_token(access_token_data)
        refresh_token = create_refresh_token(refresh_token_data)
        
        # Додаємо заголовки rate limit
        await add_rate_limit_headers(request, response)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
            
    except JWTError:
        raise credentials_exception