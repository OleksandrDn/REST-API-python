from fastapi import APIRouter, Depends, Query, HTTPException, Path, status, Request, Response
from bson import ObjectId
from datetime import datetime
from typing import List

from app.database import get_database
from app.models import BookInput, BookResponse, PaginatedBooksResponse
from app.security import get_current_user
from app.rate_limiter import authenticated_rate_limit_dependency

router = APIRouter()

async def add_rate_limit_headers(request: Request, response: Response):
    """Додає заголовки rate limit до відповіді"""
    if hasattr(request.state, 'rate_limit_headers'):
        for key, value in request.state.rate_limit_headers.items():
            response.headers[key] = value

@router.get("/", tags=["base"])
async def index():
    """Головна сторінка API бібліотеки"""
    return {"message": "Головна сторінка API бібліотеки"}

@router.get("/books", response_model=PaginatedBooksResponse, tags=["books"])
async def get_books(
    request: Request,
    response: Response,
    skip: int = Query(0, ge=0, description="Кількість записів для пропуску"),
    limit: int = Query(10, ge=1, le=100, description="Максимальна кількість записів для отримання"),
    db=Depends(get_database),
    current_user=Depends(get_current_user),  # Вимагаємо аутентифікації
    _=Depends(lambda r, u: authenticated_rate_limit_dependency(r, u))  # Rate limiting
):
    """
    Отримати список книг з пагінацією
    """
    books_collection = db["books"]
    total = await books_collection.count_documents({})
    cursor = books_collection.find().skip(skip).limit(limit)
    books = [convert_book_from_db(book) async for book in cursor]
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    return {"data": books, "total": total, "skip": skip, "limit": limit}

@router.post("/books", response_model=List[BookResponse], status_code=201, tags=["books"])
async def add_books(
    request: Request,
    response: Response,
    payload: List[BookInput],
    db=Depends(get_database),
    current_user=Depends(get_current_user),  # Вимагаємо аутентифікації
    _=Depends(lambda r, u: authenticated_rate_limit_dependency(r, u))  # Rate limiting
):
    """
    Додати нові книги
    """
    now = datetime.utcnow()
    books_collection = db["books"]
    
    # Додаємо інформацію про користувача, який додав книги
    docs = [{
        **book.dict(), 
        "created_at": now, 
        "updated_at": None,
        "created_by": current_user["_id"]  # ID користувача, який додав книгу
    } for book in payload]
    
    result = await books_collection.insert_many(docs)
    inserted_books = await books_collection.find({"_id": {"$in": result.inserted_ids}}).to_list(length=len(docs))
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    return [convert_book_from_db(book) for book in inserted_books]

@router.get("/books/{book_id}", response_model=BookResponse, tags=["books"])
async def get_book(
    request: Request,
    response: Response,
    book_id: str = Path(..., description="ID книги"),
    db=Depends(get_database),
    current_user=Depends(get_current_user),  # Вимагаємо аутентифікації
    _=Depends(lambda r, u: authenticated_rate_limit_dependency(r, u))  # Rate limiting
):
    """
    Отримати книгу за ID
    """
    if not ObjectId.is_valid(book_id):
        raise HTTPException(status_code=400, detail="Невірний формат ID")
    
    book = await db["books"].find_one({"_id": ObjectId(book_id)})
    if not book:
        raise HTTPException(status_code=404, detail="Книга не знайдена")
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    return convert_book_from_db(book)

@router.put("/books/{book_id}", response_model=BookResponse, tags=["books"])
async def update_book(
    request: Request,
    response: Response,
    book_id: str = Path(..., description="ID книги"),
    payload: BookInput = ...,
    db=Depends(get_database),
    current_user=Depends(get_current_user),  # Вимагаємо аутентифікації
    _=Depends(lambda r, u: authenticated_rate_limit_dependency(r, u))  # Rate limiting
):
    """
    Оновити книгу за ID
    """
    if not ObjectId.is_valid(book_id):
        raise HTTPException(status_code=400, detail="Невірний формат ID")
    
    update_data = payload.dict()
    update_data["updated_at"] = datetime.utcnow()
    update_data["updated_by"] = current_user["_id"]  # ID користувача, який оновив книгу
    
    result = await db["books"].update_one({"_id": ObjectId(book_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Книга не знайдена")
    
    updated = await db["books"].find_one({"_id": ObjectId(book_id)})
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    return convert_book_from_db(updated)

@router.delete("/books/{book_id}", status_code=204, tags=["books"])
async def delete_book(
    request: Request,
    response: Response,
    book_id: str = Path(..., description="ID книги"),
    db=Depends(get_database),
    current_user=Depends(get_current_user),  # Вимагаємо аутентифікації
    _=Depends(lambda r, u: authenticated_rate_limit_dependency(r, u))  # Rate limiting
):
    """
    Видалити книгу за ID
    """
    if not ObjectId.is_valid(book_id):
        raise HTTPException(status_code=400, detail="Невірний формат ID")
    
    result = await db["books"].delete_one({"_id": ObjectId(book_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Книга не знайдена")
    
    # Додаємо заголовки rate limit
    await add_rate_limit_headers(request, response)
    
    return None

def convert_book_from_db(book) -> BookResponse:
    """Конвертує документ MongoDB в об'єкт моделі"""
    return BookResponse(
        id=str(book["_id"]),
        title=book["title"],
        author=book["author"],
        year=book.get("year"),
        isbn=book.get("isbn"),
        description=book.get("description"),
        created_at=book["created_at"],
        updated_at=book.get("updated_at")
    )