
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from bson import ObjectId

# Імпортуємо get_database на початку файлу
from app.database import get_database


# Моделі для аутентифікації
class UserCreate(BaseModel):
    """Модель для створення користувача"""
    email: EmailStr = Field(..., description="Email користувача")
    username: str = Field(..., min_length=3, max_length=50, description="Ім'я користувача")
    password: str = Field(..., min_length=6, description="Пароль користувача")

class UserLogin(BaseModel):
    """Модель для входу користувача"""
    email: EmailStr = Field(..., description="Email користувача")
    password: str = Field(..., description="Пароль користувача")

class UserResponse(BaseModel):
    """Модель відповіді з даними користувача"""
    id: str = Field(..., description="Унікальний ідентифікатор користувача")
    email: EmailStr = Field(..., description="Email користувача")
    username: str = Field(..., description="Ім'я користувача")
    created_at: datetime = Field(..., description="Дата створення")
    updated_at: Optional[datetime] = Field(None, description="Дата оновлення")

class Token(BaseModel):
    """Модель відповіді з токенами доступу"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Модель для даних токена"""
    user_id: Optional[str] = None
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-placeholder-change-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ALGORITHM = "HS256"

# OAuth2 схема для отримання токена з заголовка Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Контекст для хешування паролів
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Перевіряє відповідність пароля хешу"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Створює хеш з пароля"""
    return pwd_context.hash(password)

def create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    """Створює JWT токен з даними та терміном дії"""
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(data: Dict[str, Any]) -> str:
    """Створює access token"""
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(data, expires_delta)

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Створює refresh token"""
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(data, expires_delta)

async def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_database)):
    """
    Отримує поточного користувача за токеном
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Невірні дані аутентифікації",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Декодуємо JWT токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
        
    # Отримуємо користувача з бази даних
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
        
    # Видаляємо пароль з об'єкта користувача
    user.pop("password", None)
    return user