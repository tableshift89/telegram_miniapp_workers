import requests
import json

# Список працівників для цеху ДМТ
dmt_workers = [
    "Коваленко Андрій Миколайович",
    "Шевченко Ольга Петрівна",
    "Бондаренко Сергій Іванович",
    "Мельник Тетяна Володимирівна",
    "Лисенко Віктор Олексійович"
]

# Список працівників для цеху Пакування
pack_workers = [
    "Гончаренко Ірина Василівна",
    "Руденко Олег Михайлович",
    "Ткаченко Наталія Сергіївна",
    "Кравчук Дмитро Андрійович",
    "Савченко Людмила Ігорівна"
]

url = "https://telegram-miniapp-workers.onrender.com/api/worker"

print("Додаємо працівників для цеху ДМТ...")
for worker in dmt_workers:
    response = requests.post(url, json={"fullname": worker, "workshop": "DMT"})
    if response.status_code == 200:
        print(f"✅ Додано: {worker}")
    else:
        print(f"❌ Помилка: {worker} - {response.text}")

print("\nДодаємо працівників для цеху Пакування...")
for worker in pack_workers:
    response = requests.post(url, json={"fullname": worker, "workshop": "Пакування"})
    if response.status_code == 200:
        print(f"✅ Додано: {worker}")
    else:
        print(f"❌ Помилка: {worker} - {response.text}")

print("\n🎉 Готово!")
