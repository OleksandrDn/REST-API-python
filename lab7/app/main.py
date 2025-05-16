from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router as router
from app.auth_routes import router as auth_router
from app.database import connect_to_mongo, close_mongo_connection

# Створення екземпляру FastAPI
app = FastAPI(
    title="Бібліотека API",
    description="API для управління книгами в бібліотеці з аутентифікацією",
    version="1.0.0",
    contact={"email": "example@example.com"},
    openapi_tags=[
        {"name": "books", "description": "Операції з книгами"},
        {"name": "base", "description": "Базові операції"},
        {"name": "auth", "description": "Аутентифікація та авторизація"},
    ]
)

# Додавання CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для продакшену рекомендується вказати конкретні домени
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подія запуску додатку
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

# Подія завершення роботи додатку
@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# Включення маршрутів
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(router, prefix="/api")