from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class BookInput(BaseModel):
    """Модель для створення або оновлення книги"""
    title: str = Field(..., description="Назва книги")
    author: str = Field(..., description="Автор книги")
    year: Optional[int] = Field(default=None, ge=0, le=2100, description="Рік видання")
    isbn: Optional[str] = Field(default=None, description="ISBN код книги")
    description: Optional[str] = Field(default=None, description="Опис книги")

class BookResponse(BookInput):
    """Модель для відповіді з даними про книгу"""
    id: str = Field(..., description="Унікальний ідентифікатор книги")
    created_at: datetime = Field(..., description="Дата створення запису")
    updated_at: Optional[datetime] = Field(default=None, description="Дата останнього оновлення")

class PaginatedBooksResponse(BaseModel):
    """Модель для відповіді зі списком книг з пагінацією"""
    data: List[BookResponse]
    total: int
    skip: int
    limit: int