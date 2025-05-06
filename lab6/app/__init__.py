from flask import Flask
from flasgger import Swagger
from app.database import initialize_db

def create_app():
    """Створення Flask додатку"""
    app = Flask(__name__)

    # Підключення до MongoDB
    db = initialize_db()  # Викликаємо функцію для підключення до БД
    if db is None:
        raise Exception("Не вдалося підключитися до бази даних MongoDB.")

    # Імпортуємо маршрути та визначення моделей
    from app.routes import api_bp, register_routes, definitions

    # Налаштування Swagger
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/swagger/"
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Бібліотека API",
            "description": "API для управління книгами в бібліотеці",
            "version": "1.0.0",
            "contact": {
                "email": "example@example.com"
            }
        },
        "basePath": "/api",
        "schemes": [
            "http",
            "https"
        ],
        "tags": [
            {
                "name": "books",
                "description": "Операції з книгами"
            },
            {
                "name": "base",
                "description": "Базові операції"
            }
        ],
        "definitions": definitions
    }

    # Реєстрація маршрутів з передачею бази даних
    register_routes(db)
    
    # Реєстрація Blueprint з префіксом /api
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Ініціалізація Swagger після реєстрації всіх маршрутів
    Swagger(app, config=swagger_config, template=swagger_template)

    return app