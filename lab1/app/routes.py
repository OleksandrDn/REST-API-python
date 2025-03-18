from flask import request, jsonify
from app import app
from app.models import books
from app.schemas import book_schema
from marshmallow import ValidationError

@app.route('/books', methods=['GET'])
def get_books():
    return jsonify(books)

@app.route('/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = next((b for b in books if b['id'] == book_id), None)
    return jsonify(book) if book else (jsonify({"error": "Book not found"}), 404)

@app.route('/books', methods=['POST'])
def add_book():
    try:
        book = book_schema.load(request.json)
        if any(b['id'] == book['id'] for b in books):
            return jsonify({"error": "Book with this ID already exists"}), 400
        books.append(book)
        return jsonify(book), 201
    except ValidationError as err:
        return jsonify(err.messages), 400

@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    global books
    books = [b for b in books if b['id'] != book_id]
    return jsonify({"message": "Book deleted"})
