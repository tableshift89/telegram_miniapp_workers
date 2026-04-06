# Використовуємо конкретну стабільну версію Python
FROM python:3.11.8-slim

WORKDIR /app

# Встановлюємо необхідні системні пакети для компіляції
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо файл із залежностями
COPY requirements.txt .

# Оновлюємо pip та встановлюємо пакети
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проекту
COPY . .

# Створюємо необхідні директорії (якщо їх немає)
RUN mkdir -p app/static app/templates

# Відкриваємо порт
EXPOSE 8000

# Команда для запуску
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
