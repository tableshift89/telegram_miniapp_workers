# Використовуємо повністю конкретну версію Python 3.11
FROM python:3.11.8-slim-bookworm

WORKDIR /app

# Встановлюємо необхідні системні пакети
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо та встановлюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Копіюємо код
COPY . .

# Створюємо необхідні директорії
RUN mkdir -p app/static app/templates

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
