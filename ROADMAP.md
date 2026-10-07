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

- [x] Lead formasida faqat tanlangan mijozga tegishli kontaktlarni ko'rsatish.
- [x] Katta mijozlar va kontaktlar ro'yxatida qidiriladigan tanlov qo'shish.
- [x] Taklif formasida ham mijozga bog'liq kontakt tanlovidan foydalanish.
- [x] Formadagi inglizcha maydon nomlarini o'zbekchalashtirish.

**Tayyorlik mezoni:** noto'g'ri mijoz-kontakt juftligini saqlab bo'lmaydi va
katta ro'yxatdan kerakli yozuv tez topiladi.

### P0 — To'liq savdo oqimini sinash

- [x] `Mijoz → Lead → Taklif → PDF → Buyurtma` oqimini brauzerda sinash.
- [x] Tenant chegarasi, noto'g'ri qiymatlar va ruxsatlarni test qilish.
- [x] Barcha Django va JavaScript tekshiruvlarini o'tkazish.

**Tayyorlik mezoni:** asosiy savdo oqimi xatosiz yakunlanadi, boshqa
tashkilot ma'lumotiga kirib bo'lmaydi va avtomatik testlar muvaffaqiyatli o'tadi.

### P1 — Kommunikatsiya poydevori

- [x] Email orqali taklif yuborish va yuborilgan vaqtni qayd qilish.
- [x] Har bir sotuvchi uchun IMAP va SMTP sozlamalarini qo'lda kiritish.
- [x] Email parolini shifrlab saqlash va ulanishni tekshirish.
- [x] Taklifni sotuvchining tanlangan shaxsiy SMTP akkauntidan yuborish.
- [x] Mijoz bilan aloqa tarixini yagona timeline'da ko'rsatish.
- [x] Yuborilgan taklif uchun avtomatik follow-up vazifasi yaratish.
- [ ] IMAP orqali kiruvchi xatlarni sinxronlash va Lead bilan bog'lash.
- [ ] Telegram va WhatsApp integratsiyasining xavfsiz usulini aniqlash.

**Tayyorlik mezoni:** sotuvchi kamida email yuborilishini CRM'da qayd etadi,
aloqa tarixini ko'radi va keyingi bog'lanish vazifasini unutmaydi.

### P2 — Boshlang'ich savdo hisobotlari

- [x] Savdo voronkasi konversiyasi va yutqazish sabablarini ko'rsatish.
- [x] Menejer, yo'nalish va davr bo'yicha filtrlash qo'shish.
- [x] Rejadagi va haqiqiy tushum uchun ma'lumot modelini aniqlash.

**Tayyorlik mezoni:** rahbar joriy savdo voronkasi, yutuq va yo'qotishlarni
bitta sahifada ko'ra oladi.

### P0 — Xodimlar va kirish xavfsizligi

- [x] Direktor va tashkilot egasi uchun xodim qo'shish hamda tahrirlash.
- [x] Yangi xodimni vaqtinchalik parol bilan yaratish.
- [x] Birinchi kirishda parolni majburiy almashtirish.
- [x] Lavozimlar bo'yicha sahifa va yozish amallarini cheklash.
- [x] Bloklangan xodimning faol sessiyasini avtomatik tugatish.

**Tayyorlik mezoni:** yangi xodim xavfsiz tarzda tizimga kiradi, faqat o'z
lavozimiga ruxsat berilgan amallarni bajaradi va bloklanganda tizimdan chiqadi.

### Kun yakuni

- [x] Ertangi sprint natijalarini brauzerda qayta tekshirish.
- [x] `ROADMAP.md` belgilari va keyingi ustuvor vazifalarni yangilash.
- [ ] Alohida tasdiqdan keyin commit va GitHub'ga push qilish.

## Sprint — 2026-yil 2-oktyabr

Sprint maqsadi: narxlar tarixini yo'qotmasdan boshqarish va savdo taklifiga
amaldagi narxni xavfsiz olib o'tish.

- [x] Sidebar va asosiy ichki amallar uchun umumiy SVG ikonka tizimini qo'shish.
- [x] Tashkilot konteksti va ruxsatlarni barcha ichki sahifalarda barqaror qilish.
- [x] Price-list hujjatlariga versiya raqami va faol/arxiv hayot siklini qo'shish.
- [x] Yangi versiyani avvalgi hujjat va mahsulot qatorlaridan nusxalash.
- [x] Bir segmentda yangi versiya faollashganda eskisini avtomatik arxivlash.
- [x] Tijorat taklifiga faol price-list narxini valyuta, muddat va miqdor bo'yicha olish.
- [x] Avtomatik narx qo'lda o'zgartirilganda sabab va narx manbasini saqlash.
- [x] Narxlar uchun to'rt kasr aniqligini taklif va buyurtmagacha saqlash.
- [x] Migratsiyalar, avtomatik testlar va brauzer tekshiruvini bajarish.

**Tayyorlik mezoni:** sotuvchi price-listning yangi versiyasini eski hujjatdan
yaratadi, faollashtiradi va tijorat taklifiga shu versiyadagi amaldagi narx
avtomatik tushadi; har qanday qo'lda o'zgarish sababi bilan qayd etiladi.

## Sprint — 2026-yil 3-oktyabr

Sprint maqsadi: jismoniy shaxslarni faqat mijoz kompaniyasi ichida emas,
mustaqil CRM kontakti sifatida ham boshqarish.

- [x] Kompaniyaga bog'lanishi ixtiyoriy bo'lgan universal kontakt modelini yaratish.
- [x] Kontakt turi, hudud, manba, teglar, mas'ul va holat maydonlarini qo'shish.
- [x] Kontaktlar uchun alohida sidebar bo'limi, filtr va pagination yaratish.
- [x] Kontakt profili, aloqa tarixi va bog'langan Leadlarni ko'rsatish.
- [x] Kontaktdan avtomatik to'ldirilgan Lead va vazifa yaratish oqimini qo'shish.
- [x] Telefon va email bo'yicha tashkilot ichidagi dublikatlarni tekshirish.
- [x] Eski kontaktlarni saqlagan holda migratsiya va avtomatik testlarni bajarish.

**Tayyorlik mezoni:** mijoz, yetkazib beruvchi, hamkor yoki boshqa vakil
kompaniyasiz ham kontakt sifatida saqlanadi; undan Lead va vazifa yaratiladi,
barcha aloqa tarixi yagona profilda ko'rinadi.

## Keyingi bosqichlar

### Savdo va kommunikatsiya

- [x] Email orqali taklif yuborish va yuborilgan vaqtni qayd qilish.
- [x] Sotuvchining shaxsiy IMAP va SMTP akkauntini xavfsiz ulash.
- [ ] IMAP orqali kiruvchi javoblarni avtomatik sinxronlash.
- [ ] Telegram va WhatsApp uchun xavfsiz integratsiya variantini tanlash.
- [x] Mijoz bilan barcha aloqalarni yagona timeline'da ko'rsatish.
- [x] Follow-up vazifalarini avtomatik yaratish.
- [ ] Ichki chatni mijozlar uchun Xabarlar markazidan ajratib, alohida
  "Jamoa chatlari" bo'limiga ko'chirish va Xabarlar sahifasidagi chalkash
  yangi suhbat tugmasini olib tashlash.
- [ ] Mutlaq real-time yangilanishlar uchun Django Channels, WebSocket va Redis
  infratuzilmasiga o'tish.

### Mahsulot va narxlar

- [x] Price-list va product-list uchun logotipli PDF hamda hujjat muharriri.
- [x] Tayyor kiyim-kechak kategoriyasi va Product List'da o'lcham/rang matritsasini yakunlash.
- [ ] Price-list versiyalari va amal qilish muddatlarini boshqarish.
- [ ] Mijoz, bozor va hajm bo'yicha individual narx qoidalarini qo'shish.
- [ ] Ombor qoldig'i va ishlab chiqarish muddati bilan integratsiya qilish.

### Hisobot va boshqaruv

- [x] Savdo voronkasi konversiyasi va yo'qotish sabablarini ko'rsatish.
- [x] Menejer, yo'nalish va davr bo'yicha savdo hisobotlarini yaratish.
- [x] Rejadagi va haqiqiy tushumni taqqoslash.
- [x] To'lov rejalari va tushumlarni tahrirlash hamda sabab bilan bekor qilish.
- [x] Moliyaviy o'zgarishlar tarixini saqlash va kechikkan to'lovlarni ko'rsatish.
- [x] 7/30 kunlik pul oqimi prognozi va to'lov filtrlarini qo'shish.
- [ ] Moliyaviy hisobotlarni Excel va PDF formatida eksport qilish.
- [x] Rollar va amallar bo'yicha batafsil ruxsat tizimini qo'shish.

## Ishlash tartibi

1. Sprint boshida ushbu ro'yxatdan vazifalar tanlanadi.
2. Katta vazifa uchun GitHub Issue ochilib, shu hujjatga havola qo'shiladi.
3. Ish jarayoni `Rejada → Jarayonda → Tekshiruv → Tayyor` holatlarida yuritiladi.
4. Vazifa test va brauzer tekshiruvidan o'tgandan keyingina bajarilgan deb
   belgilanadi.
5. Commit, push va deploy alohida tasdiqdan keyin bajariladi.
