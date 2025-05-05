from typing import Optional
from datetime import datetime
from beanie import Document
from pydantic import Field

class Book(Document):
    """Модель книги з використанням Beanie"""
    title: str = Field(..., description="Назва книги")
    author: str = Field(..., description="Автор книги")
    year: Optional[int] = Field(None, description="Рік публікації", ge=0, le=2100)
    isbn: Optional[str] = Field(None, description="ISBN книги")
    description: Optional[str] = Field(None, description="Опис книги")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    class Settings:
        name = "books"  
