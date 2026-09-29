# BCRM rivojlanish rejasi

Ushbu hujjat Bunyodkor Textile CRM loyihasining ustuvor vazifalari va
yaqin sprintlarini saqlaydi. Vazifa bajarilganda belgi `[x]` holatiga
o'zgartiriladi; katta vazifalar keyinchalik alohida GitHub Issue sifatida
ochiladi.

## Sprint — 2026-yil 29-sentabr

Sprint maqsadi: mijozdan boshlangan savdo jarayonini Lead, savdo taklifi va
buyurtmagacha uzluksiz ishlaydigan holatga keltirish.

### P0 — Markaziy tashkilot sozlamalari

- [x] Tashkilot, bank va aloqa rekvizitlarini bir joydan boshqarish.
- [x] Logotip, imzo va muhr rasmlarini xavfsiz yuklash.
- [x] Standart valyuta, Incoterm, to'lov va yetkazish shartlarini saqlash.
- [x] Taklif va buyurtma raqami prefikslarini boshqarish.
- [x] PDF shablonini tashkilot rekvizitlari bilan bog'lash.

**Tayyorlik mezoni:** tashkilot egasi yoki direktori sozlamalarni interfeysdan
o'zgartiradi va yangi savdo hujjatlari ushbu qiymatlardan foydalanadi.

### P0 — Lead'dan savdo taklifi yaratish

- [x] Lead tafsilotiga `Savdo taklifi yaratish` amalini qo'shish.
- [x] Lead'dagi mijoz, kontakt, mas'ul xodim va valyutani avtomatik ko'chirish.
- [x] Katalogdan mahsulot va variantlarni taklifga qo'shish.
- [x] Miqdor, birlik narxi, chegirma va jami qiymatni hisoblash.
- [x] Bir Lead uchun yaratilgan takliflar tarixini ko'rsatish.

**Tayyorlik mezoni:** foydalanuvchi Lead sahifasidan chiqmasdan yangi taklif
yarata oladi va yaratilgan taklif Lead bilan bog'lanadi.

### P0 — Savdo taklifini PDF ko'rinishida tayyorlash

- [x] Bunyodkor Textile rekvizitlari uchun PDF shablon yaratish.
- [x] Trikotaj mato, to'quv mato va ip-kalava xususiyatlarini mos jadvalda
  chiqarish.
- [x] Narx, valyuta, Incoterms, to'lov va yetkazish shartlarini ko'rsatish.
- [x] Telegram, WhatsApp va email orqali yuborishga mos fayl nomi yaratish.
- [x] Sotuvchi uchun vizual hujjat muharriri va mahsulot qatorlarini tahrirlash.

**Tayyorlik mezoni:** savdo taklifidan bir tugma orqali to'g'ri formatlangan
PDF olinadi.

### P1 — Lead bosqichlari va yakuniy holatlar

- [x] `stage` va `status` o'rtasidagi biznes qoidalarini aniqlash.
- [x] Lead `Yutildi` holatiga o'tganda buyurtma yaratish amalini ko'rsatish.
- [x] Lead `Yutqazildi` holatiga o'tganda sababni majburiy so'rash.
- [x] Kanban orqali ko'chirishda ushbu qoidalarni ham tekshirish.

**Tayyorlik mezoni:** yopilgan Lead'larda bosqich va holat bir-biriga zid
bo'lmaydi.

## Ertangi sprint — 2026-yil 30-sentabr

Sprint maqsadi: savdo formasini tez va xatosiz ishlaydigan qilish, yakuniy
oqimni tekshirish hamda kommunikatsiya va hisobotlar uchun poydevor yaratish.

### P0 — Mijoz va kontakt tanlashni yaxshilash

- [ ] Lead formasida faqat tanlangan mijozga tegishli kontaktlarni ko'rsatish.
- [ ] Katta mijozlar va kontaktlar ro'yxatida qidiriladigan tanlov qo'shish.
- [ ] Taklif formasida ham mijozga bog'liq kontakt tanlovidan foydalanish.
- [ ] Formadagi inglizcha maydon nomlarini o'zbekchalashtirish.

**Tayyorlik mezoni:** noto'g'ri mijoz-kontakt juftligini saqlab bo'lmaydi va
katta ro'yxatdan kerakli yozuv tez topiladi.

### P0 — To'liq savdo oqimini sinash

- [ ] `Mijoz → Lead → Taklif → PDF → Buyurtma` oqimini brauzerda sinash.
- [ ] Tenant chegarasi, noto'g'ri qiymatlar va ruxsatlarni test qilish.
- [ ] Barcha Django va JavaScript tekshiruvlarini o'tkazish.

**Tayyorlik mezoni:** asosiy savdo oqimi xatosiz yakunlanadi, boshqa
tashkilot ma'lumotiga kirib bo'lmaydi va avtomatik testlar muvaffaqiyatli o'tadi.

### P1 — Kommunikatsiya poydevori

- [ ] Email orqali taklif yuborish va yuborilgan vaqtni qayd qilish.
- [ ] Mijoz bilan aloqa tarixini yagona timeline'da ko'rsatish.
- [ ] Yuborilgan taklif uchun avtomatik follow-up vazifasi yaratish.
- [ ] Telegram va WhatsApp integratsiyasining xavfsiz usulini aniqlash.

**Tayyorlik mezoni:** sotuvchi kamida email yuborilishini CRM'da qayd etadi,
aloqa tarixini ko'radi va keyingi bog'lanish vazifasini unutmaydi.

### P2 — Boshlang'ich savdo hisobotlari

- [ ] Savdo voronkasi konversiyasi va yutqazish sabablarini ko'rsatish.
- [ ] Menejer, yo'nalish va davr bo'yicha filtrlash qo'shish.
- [ ] Rejadagi va haqiqiy tushum uchun ma'lumot modelini aniqlash.

**Tayyorlik mezoni:** rahbar joriy savdo voronkasi, yutuq va yo'qotishlarni
bitta sahifada ko'ra oladi.

### Kun yakuni

- [ ] Ertangi sprint natijalarini brauzerda qayta tekshirish.
- [ ] `ROADMAP.md` belgilari va keyingi ustuvor vazifalarni yangilash.
- [ ] Alohida tasdiqdan keyin commit va GitHub'ga push qilish.

## Keyingi bosqichlar

### Savdo va kommunikatsiya

- [ ] Email orqali taklif yuborish va yuborilgan vaqtni qayd qilish.
- [ ] Telegram va WhatsApp uchun xavfsiz integratsiya variantini tanlash.
- [ ] Mijoz bilan barcha aloqalarni yagona timeline'da ko'rsatish.
- [ ] Follow-up vazifalarini avtomatik yaratish.

### Mahsulot va narxlar

- [x] Price-list va product-list uchun logotipli PDF hamda hujjat muharriri.
- [ ] Tayyor kiyim-kechak kategoriyasi va o'lcham/rang matritsasini yakunlash.
- [ ] Price-list versiyalari va amal qilish muddatlarini boshqarish.
- [ ] Mijoz, bozor va hajm bo'yicha individual narx qoidalarini qo'shish.
- [ ] Ombor qoldig'i va ishlab chiqarish muddati bilan integratsiya qilish.

### Hisobot va boshqaruv

- [ ] Savdo voronkasi konversiyasi va yo'qotish sabablarini ko'rsatish.
- [ ] Menejer, yo'nalish va davr bo'yicha savdo hisobotlarini yaratish.
- [ ] Rejadagi va haqiqiy tushumni taqqoslash.
- [ ] Rollar va amallar bo'yicha batafsil ruxsat tizimini qo'shish.

## Ishlash tartibi

1. Sprint boshida ushbu ro'yxatdan vazifalar tanlanadi.
2. Katta vazifa uchun GitHub Issue ochilib, shu hujjatga havola qo'shiladi.
3. Ish jarayoni `Rejada → Jarayonda → Tekshiruv → Tayyor` holatlarida yuritiladi.
4. Vazifa test va brauzer tekshiruvidan o'tgandan keyingina bajarilgan deb
   belgilanadi.
5. Commit, push va deploy alohida tasdiqdan keyin bajariladi.
