FROM python:3.13-slim

WORKDIR /app

# Встановлення залежностей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіювання коду
COPY . .

# Змінна середовища для Flask
ENV FLASK_APP=run.py

# Відкриття порту
EXPOSE 5000

# Команда для запуску
CMD ["flask", "run", "--host=0.0.0.0"]