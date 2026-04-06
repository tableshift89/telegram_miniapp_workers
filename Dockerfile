FROM python:3.11-slim

WORKDIR /app

# Встановлюємо необхідні системні пакети
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код
COPY . .

# Запускаємо додаток
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
