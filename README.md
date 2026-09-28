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

Paketlarni o'rnatishdan oldin virtual muhit yarating, so'ng
`.env.local.example` faylini `.env.local` nomi bilan nusxalab lokal MySQL
ma'lumotlarini kiriting. Avvalgi `.env` fayli ham qo'llab-quvvatlanadi.

~~~powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
~~~

Bu repozitoriyda paketlar avtomatik o'rnatilmaydi. `.env` va `.env.local` hech
qachon Git'ga qo'shilmasligi kerak.

## Muhitlar

- `local`: standart `manage.py` muhiti, MySQL yoki SQLite bilan ishlaydi.
- `test`: pytest va avtomatik testlar uchun xotiradagi SQLite bazasi.
- `production`: WSGI/ASGI serverlarining standarti; secret, host va MySQL
  ma'lumotlarini environment orqali majburiy oladi.

Muhitni aniq tanlash uchun `BCRM_ENV` ishlatiladi:

~~~powershell
$env:BCRM_ENV = "local"
python manage.py check
~~~

Production konfiguratsiyasi uchun `.env.production.example` dagi qiymatlarni
server environment'iga kiriting. Production sozlamalari lokal `.env` faylini
avtomatik o'qimaydi.

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
