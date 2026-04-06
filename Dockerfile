FROM python:3.11-slim

WORKDIR /app

# Встановлюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код
COPY . .

# Створюємо директорії для статики та шаблонів
RUN mkdir -p app/static app/templates

# Відкриваємо порт
EXPOSE 8000

# Запускаємо додаток
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
