from fastapi import FastAPI, HTTPException
from typing import List
from models import books
from schemas import Book

app = FastAPI()

def generate_book_id():
    return max(book['id'] for book in books) + 1 if books else 1

@app.get('/')
async def index():
    return "Головна сторінка"

@app.get('/books', response_model=List[Book])
async def get_books():
    return books

@app.get('/books/{book_id}', response_model=Book)
async def get_book(book_id: int):
    book = next((b for b in books if b['id'] == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Книга не знайдена")
    return book

@app.post('/books', response_model=Book, status_code=201)
async def add_book(book: Book):
    # Генеруємо ID автоматично
    book.id = generate_book_id()
    books.append(book.model_dump())
    return book

@app.delete('/books/{book_id}')
async def delete_book(book_id: int):
    global books
    
    book_to_delete = next((b for b in books if b['id'] == book_id), None)
    
    if not book_to_delete:
        raise HTTPException(status_code=404, detail="Книга не знайдена")
    
    books = [b for b in books if b['id'] != book_id]
    return {"message": "Книга видалена"}