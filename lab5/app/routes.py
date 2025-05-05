from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Dict
from datetime import datetime
from app.models import Book
from pydantic import BaseModel

router = APIRouter()

# Структура відповіді для списку книг
class BookListResponse(BaseModel):
    data: List[Book]
    total: int
    skip: int
    limit: int

@router.get("/")
async def index():
    return {"message": "Головна сторінка API бібліотеки"}

@router.post("/books", status_code=201, response_model=List[Book])
async def add_books_bulk(books: List[Book]):
    if not books:
        raise HTTPException(status_code=400, detail="Потрібно надати хоча б одну книгу")

    now = datetime.utcnow()
    inserted_books = []
    
    for book in books:
        book.created_at = now
        book.updated_at = None
        await book.insert()
        inserted_books.append(book)

    return inserted_books

@router.get("/books", response_model=BookListResponse)
async def get_all_books(skip: int = Query(0, ge=0), limit: int = Query(10, le=100)):
    """
    Повертає список книг з пагінацією і метаінформацією.
    - `skip`: кількість пропущених документів (сторінка)
    - `limit`: кількість книг на сторінці
    """
    
    books = await Book.find_all().skip(skip).limit(limit).to_list()

    
    total_count = await Book.find().count()

    return BookListResponse(data=books, total=total_count, skip=skip, limit=limit)

@router.put("/books/{book_id}", response_model=Book)
async def update_book(book_id: str, book_data: Book):
    existing = await Book.get(book_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Книга не знайдена")
    
    update_data = book_data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    
    await existing.update({"$set": update_data})
    return await Book.get(book_id)

@router.delete("/books/{book_id}")
async def delete_book(book_id: str):
    book = await Book.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Книга не знайдена")
    
    await book.delete()
    return JSONResponse(status_code=200, content={"message": "Книга видалена"})

# Додана функція register_routes для підключення роутерів до головного додатку
def register_routes(app):
    """
    Реєструє всі маршрути API
    """
    app.include_router(router, prefix="/api")
