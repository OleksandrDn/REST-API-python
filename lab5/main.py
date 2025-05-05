from fastapi import FastAPI, HTTPException
from app.routes import register_routes
from app.database import check_connection
import uvicorn

app = FastAPI(title="Бібліотека API", 
              description="API для управління книгами в бібліотеці", 
              version="1.0.0")

# Реєстрація маршрутів
register_routes(app)

@app.on_event("startup")
async def startup_db_client():
    # Перевірка з'єднання з MongoDB при запуску додатку
    if not await check_connection():
        print("ПОПЕРЕДЖЕННЯ: Неможливо підключитися до MongoDB!")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
