from flask import request, Blueprint, jsonify
from flask_restful import Resource, Api
from datetime import datetime
from bson.objectid import ObjectId
from app.models import BookSchema

book_schema = BookSchema()
book_list_schema = BookSchema(many=True)

# Створюємо Blueprint
api_bp = Blueprint('api', __name__)
api = Api(api_bp)

class Index(Resource):
    def get(self):
        """
        Головна сторінка API
        ---
        tags:
          - base
        responses:
          200:
            description: Успішна відповідь
            schema:
              properties:
                message:
                  type: string
                  description: Вітальне повідомлення
        """
        return {"message": "Головна сторінка API бібліотеки"}

class BookList(Resource):
    def __init__(self, books_collection):
        self.books_collection = books_collection

    def get(self):
        """
        Отримати список книг
        ---
        tags:
          - books
        parameters:
          - name: skip
            in: query
            type: integer
            default: 0
            description: Кількість записів для пропуску (пагінація)
          - name: limit
            in: query
            type: integer
            default: 10
            description: Максимальна кількість записів для повернення
        responses:
          200:
            description: Список книг
            schema:
              properties:
                data:
                  type: array
                  items:
                    $ref: '#/definitions/Book'
                total:
                  type: integer
                  description: Загальна кількість книг
                skip:
                  type: integer
                  description: Кількість пропущених записів
                limit:
                  type: integer
                  description: Обмеження на кількість записів
        """
        try:
            # Отримуємо параметри пагінації
            skip = int(request.args.get("skip", 0))
            limit = int(request.args.get("limit", 10))
            
            # Перевіряємо, що параметри пагінації валідні
            if skip < 0:
                skip = 0
            if limit < 1:
                limit = 10
            if limit > 100:  # Обмеження максимальної кількості записів
                limit = 100
                
            # Отримуємо загальну кількість книг
            total = self.books_collection.count_documents({})
            
            # Отримуємо дані з бази даних з пагінацією
            cursor = self.books_collection.find().skip(skip).limit(limit)
            books = list(cursor)
            
            # Конвертуємо ObjectId в строки для JSON серіалізації
            for book in books:
                book["_id"] = str(book["_id"])
                
            # Серіалізуємо дані за допомогою схеми
            serialized_books = book_list_schema.dump(books)
            
            return {
                "data": serialized_books,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        except Exception as e:
            return {"error": str(e)}, 500

    def post(self):
        """
        Додати нові книги
        ---
        tags:
          - books
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: array
              items:
                $ref: '#/definitions/BookInput'
        responses:
          201:
            description: Книги успішно додані
            schema:
              type: array
              items:
                $ref: '#/definitions/Book'
          400:
            description: Помилка валідації
            schema:
              properties:
                message:
                  type: string
        """
        try:
            # Отримуємо дані з запиту
            books_data = request.get_json()
            
            # Перевіряємо, що дані отримані
            if not books_data:
                return {"message": "Потрібно надати хоча б одну книгу"}, 400
                
            # Перевіряємо, що отримали список
            if not isinstance(books_data, list):
                books_data = [books_data]  # Якщо отримали одну книгу, конвертуємо в список
                
            # Додаємо метадані
            now = datetime.utcnow()
            for book in books_data:
                book["created_at"] = now
                book["updated_at"] = None
                
            # Додаємо книги до бази даних
            result = self.books_collection.insert_many(books_data)
            
            # Отримуємо додані книги з бази даних
            inserted_books = list(self.books_collection.find({"_id": {"$in": result.inserted_ids}}))
            
            # Конвертуємо ObjectId в строки
            for book in inserted_books:
                book["_id"] = str(book["_id"])
                
            # Серіалізуємо дані за допомогою схеми
            serialized_books = book_list_schema.dump(inserted_books)
            
            return serialized_books, 201
        except Exception as e:
            return {"error": str(e)}, 500

class BookItem(Resource):
    def __init__(self, books_collection):
        self.books_collection = books_collection
    
    def get(self, book_id):
        """
        Отримати книгу за ID
        ---
        tags:
          - books
        parameters:
          - name: book_id
            in: path
            required: true
            type: string
            description: ID книги
        responses:
          200:
            description: Книга знайдена
            schema:
              $ref: '#/definitions/Book'
          404:
            description: Книга не знайдена
            schema:
              properties:
                message:
                  type: string
        """
        try:
            # Перевіряємо, що ID має правильний формат
            if not ObjectId.is_valid(book_id):
                return {"message": "Невірний формат ID"}, 400
                
            # Шукаємо книгу
            book = self.books_collection.find_one({"_id": ObjectId(book_id)})
            
            # Перевіряємо, що книга знайдена
            if not book:
                return {"message": "Книга не знайдена"}, 404
                
            # Конвертуємо ObjectId в строку
            book["_id"] = str(book["_id"])
            
            # Серіалізуємо дані за допомогою схеми
            serialized_book = book_schema.dump(book)
            
            return serialized_book, 200
        except Exception as e:
            return {"error": str(e)}, 500

    def put(self, book_id):
        """
        Оновити книгу
        ---
        tags:
          - books
        parameters:
          - name: book_id
            in: path
            required: true
            type: string
            description: ID книги
          - in: body
            name: body
            required: true
            schema:
              $ref: '#/definitions/BookInput'
        responses:
          200:
            description: Книга успішно оновлена
            schema:
              $ref: '#/definitions/Book'
          404:
            description: Книга не знайдена
            schema:
              properties:
                message:
                  type: string
        """
        try:
            # Перевіряємо, що ID має правильний формат
            if not ObjectId.is_valid(book_id):
                return {"message": "Невірний формат ID"}, 400
                
            # Отримуємо дані для оновлення
            book_data = request.get_json()
            if not book_data:
                return {"message": "Не надано даних для оновлення"}, 400
                
            # Додаємо метадані
            book_data["updated_at"] = datetime.utcnow()
            
            # Оновлюємо книгу
            result = self.books_collection.update_one(
                {"_id": ObjectId(book_id)},
                {"$set": book_data}
            )
            
            # Перевіряємо, що книга існує
            if result.matched_count == 0:
                return {"message": "Книга не знайдена"}, 404
                
            # Отримуємо оновлену книгу
            updated_book = self.books_collection.find_one({"_id": ObjectId(book_id)})
            
            # Конвертуємо ObjectId в строку
            updated_book["_id"] = str(updated_book["_id"])
            
            # Серіалізуємо дані за допомогою схеми
            serialized_book = book_schema.dump(updated_book)
            
            return serialized_book, 200
        except Exception as e:
            return {"error": str(e)}, 500

    def delete(self, book_id):
        """
        Видалити книгу
        ---
        tags:
          - books
        parameters:
          - name: book_id
            in: path
            required: true
            type: string
            description: ID книги
        responses:
          200:
            description: Книга успішно видалена
            schema:
              properties:
                message:
                  type: string
          404:
            description: Книга не знайдена
            schema:
              properties:
                message:
                  type: string
        """
        try:
            # Перевіряємо, що ID має правильний формат
            if not ObjectId.is_valid(book_id):
                return {"message": "Невірний формат ID"}, 400
                
            # Видаляємо книгу
            result = self.books_collection.delete_one({"_id": ObjectId(book_id)})
            
            # Перевіряємо, що книга існує
            if result.deleted_count == 0:
                return {"message": "Книга не знайдена"}, 404
                
            return {"message": "Книга видалена"}, 200
        except Exception as e:
            return {"error": str(e)}, 500

# Визначення моделей для Swagger
definitions = {
    'BookInput': {
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'description': 'Назва книги'},
            'author': {'type': 'string', 'description': 'Автор книги'},
            'year': {'type': 'integer', 'description': 'Рік видання'},
            'isbn': {'type': 'string', 'description': 'ISBN книги'},
            'description': {'type': 'string', 'description': 'Опис книги'}
        },
        'required': ['title', 'author']
    },
    'Book': {
        'type': 'object',
        'properties': {
            '_id': {'type': 'string', 'description': 'Ідентифікатор книги'},
            'title': {'type': 'string', 'description': 'Назва книги'},
            'author': {'type': 'string', 'description': 'Автор книги'},
            'year': {'type': 'integer', 'description': 'Рік видання'},
            'isbn': {'type': 'string', 'description': 'ISBN книги'},
            'description': {'type': 'string', 'description': 'Опис книги'},
            'created_at': {'type': 'string', 'format': 'date-time', 'description': 'Дата створення запису'},
            'updated_at': {'type': 'string', 'format': 'date-time', 'description': 'Дата останнього оновлення'}
        }
    }
}

# Реєстрація маршрутів
def register_routes(db):
    books_collection = db.books
    api.add_resource(Index, '/')
    api.add_resource(BookList, '/books', resource_class_kwargs={"books_collection": books_collection})
    api.add_resource(BookItem, '/books/<string:book_id>', resource_class_kwargs={"books_collection": books_collection})