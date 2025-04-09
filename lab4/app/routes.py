from flask import request, jsonify, current_app, url_for
from app.database import db
from app.models import Book
from app.schemas import book_schema, books_schema
from marshmallow import ValidationError
import base64

def register_routes(app):
    @app.route('/')
    def index():
        return "Головна сторінка API бібліотеки"

    @app.route('/books', methods=['GET'])
    def get_books():
        cursor = request.args.get('cursor', default=None)
        limit = request.args.get('limit', default=10, type=int)
        
        if limit > 100:
            limit = 100
        
        total_books = Book.query.count()
        
        query = Book.query.order_by(Book.id)
        
        if cursor:
            try:
                cursor_id = int(base64.b64decode(cursor.encode()).decode())
                query = query.filter(Book.id > cursor_id)
            except (ValueError, TypeError):
                return jsonify({"error": "Невірний формат cursor"}), 400
        
        books = query.limit(limit + 1).all()
        
        has_next = len(books) > limit
        if has_next:
            books = books[:limit]  
        
        next_cursor = None
        if has_next and books:
            last_id = books[-1].id
            next_cursor = base64.b64encode(str(last_id).encode()).decode()
        
        result = books_schema.dump(books)
        
        return jsonify({
            'data': result,
            'meta': {
                'total': total_books,
                'limit': limit,
                'next_cursor': next_cursor
            }
        })

    @app.route('/books/<int:book_id>', methods=['GET'])
    def get_book(book_id):
        book = Book.query.get(book_id)
        if not book:
            return jsonify({"error": "Книга не знайдена"}), 404
        return jsonify(book_schema.dump(book))

    @app.route('/books', methods=['POST'])
    def add_books_bulk():
        try:
            books_data = books_schema.load(request.json)

            new_books = [
                Book(title=book['title'], author=book['author'], year=book['year'])
                for book in books_data
            ]

            db.session.add_all(new_books)
            db.session.commit()

            return jsonify(books_schema.dump(new_books)), 201
        except ValidationError as err:
            return jsonify(err.messages), 400

    @app.route('/books/<int:book_id>', methods=['PUT'])
    def update_book(book_id):
        book = Book.query.get(book_id)
        if not book:
            return jsonify({"error": "Книга не знайдена"}), 404
        
        try:
            book_data = book_schema.load(request.json)
            
            book.title = book_data['title']
            book.author = book_data['author']
            book.year = book_data['year']
            
            db.session.commit()
            
            return jsonify(book_schema.dump(book))
        except ValidationError as err:
            return jsonify(err.messages), 400

    @app.route('/books/<int:book_id>', methods=['DELETE'])
    def delete_book(book_id):
        book = Book.query.get(book_id)
        if not book:
            return jsonify({"error": "Книга не знайдена"}), 404
        
        db.session.delete(book)
        db.session.commit()
        
        return jsonify({"message": "Книга видалена"}), 200