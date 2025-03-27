from flask import request, jsonify
from app import app
from app.models import books
from app.schemas import book_schema
from marshmallow import ValidationError

def generate_book_id():
    return max(book['id'] for book in books) + 1 if books else 1

@app.route('/')
def index():
    return "Головна сторінка"

@app.route('/books', methods=['GET'])
def get_books():
    return jsonify(books)

@app.route('/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = next((b for b in books if b['id'] == book_id), None)
    return jsonify(book) if book else (jsonify({"error": "Книга не знайдена"}), 404)

@app.route('/books', methods=['POST'])
def add_book():
    try:
        data = request.json.copy()
        data['id'] = generate_book_id()
        
        book = book_schema.load(data)
        books.append(book)
        return jsonify(book), 201
    except ValidationError as err:
        return jsonify(err.messages), 400

@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    global books
    
    book_to_delete = next((b for b in books if b['id'] == book_id), None)
    
    if not book_to_delete:
        return jsonify({"error": "Книга не знайдена"}), 404
    
    books = [b for b in books if b['id'] != book_id]
    return jsonify({"message": "Книга видалена"}), 200
