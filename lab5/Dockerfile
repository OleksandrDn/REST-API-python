FROM python:3.11-slim

WORKDIR /app

# Копіювання файлів залежностей
COPY requirements.txt .

# Встановлення залежностей
RUN pip install --no-cache-dir -r requirements.txt

# Копіювання коду проекту
COPY . .

# Порт для FastAPI
EXPOSE 8000

# Запуск програми
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
