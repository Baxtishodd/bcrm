# BCRM

Textile korxonalari uchun modulli CRM MVP. Birinchi bosqich mijozlar, leadlar,
pipeline, textile katalogi, takliflar va rang-o'lcham matritsasini qamrab oladi.

## Texnologiyalar

- Python 3.12+
- Django 5.2 LTS va Django REST Framework
- MySQL 8+ (utf8mb4)
- Redis va Celery (fon vazifalari uchun)
- Django Templates asosidagi responsive interfeys

## Lokal ishga tushirish

Paketlarni o'rnatishdan oldin virtual muhit yarating, so'ng .env.example faylini
.env nomi bilan nusxalab MySQL ma'lumotlarini kiriting.

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
~~~

Bu repozitoriyda paketlar avtomatik o'rnatilmaydi. .env hech qachon Git'ga
qo'shilmasligi kerak.

## Modullar

- accounts: custom foydalanuvchi modeli
- organizations: korxona, filial, a'zolik va rollar
- customers: mijoz kompaniyalari va kontaktlar
- crm: pipeline, lead va faoliyatlar
- catalog: mato, model, rang, o'lcham va variantlar
- sales: taklif, buyurtma va rang-o'lcham miqdorlari
- common: tenant-aware bazaviy modellar va dashboard

## Arxitektura qoidalari

Har bir biznes yozuvi organization bilan cheklanadi. API querysetlari joriy
foydalanuvchining faol a'zoligidan tashkilotni aniqlaydi. Muhim biznes amallari
keyinchalik services.py, murakkab o'qishlar selectors.py qatlamiga chiqariladi.

