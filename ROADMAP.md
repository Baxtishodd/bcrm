# BCRM rivojlanish rejasi

Ushbu hujjat Bunyodkor Textile CRM loyihasining ustuvor vazifalari va
yaqin sprintlarini saqlaydi. Vazifa bajarilganda belgi `[x]` holatiga
o'zgartiriladi; katta vazifalar keyinchalik alohida GitHub Issue sifatida
ochiladi.

## Ertangi sprint — 2026-yil 29-sentabr

Sprint maqsadi: mijozdan boshlangan savdo jarayonini Lead, savdo taklifi va
buyurtmagacha uzluksiz ishlaydigan holatga keltirish.

### P0 — Lead'dan savdo taklifi yaratish

- [ ] Lead tafsilotiga `Savdo taklifi yaratish` amalini qo'shish.
- [ ] Lead'dagi mijoz, kontakt, mas'ul xodim va valyutani avtomatik ko'chirish.
- [ ] Katalogdan mahsulot va variantlarni taklifga qo'shish.
- [ ] Miqdor, birlik narxi, chegirma va jami qiymatni hisoblash.
- [ ] Bir Lead uchun yaratilgan takliflar tarixini ko'rsatish.

**Tayyorlik mezoni:** foydalanuvchi Lead sahifasidan chiqmasdan yangi taklif
yarata oladi va yaratilgan taklif Lead bilan bog'lanadi.

### P0 — Savdo taklifini PDF ko'rinishida tayyorlash

- [ ] Bunyodkor Textile rekvizitlari uchun PDF shablon yaratish.
- [ ] Trikotaj mato, to'quv mato va ip-kalava xususiyatlarini mos jadvalda
  chiqarish.
- [ ] Narx, valyuta, Incoterms, to'lov va yetkazish shartlarini ko'rsatish.
- [ ] Telegram, WhatsApp va email orqali yuborishga mos fayl nomi yaratish.

**Tayyorlik mezoni:** savdo taklifidan bir tugma orqali to'g'ri formatlangan
PDF olinadi.

### P1 — Lead bosqichlari va yakuniy holatlar

- [ ] `stage` va `status` o'rtasidagi biznes qoidalarini aniqlash.
- [ ] Lead `Yutildi` holatiga o'tganda buyurtma yaratish amalini ko'rsatish.
- [ ] Lead `Yutqazildi` holatiga o'tganda sababni majburiy so'rash.
- [ ] Kanban orqali ko'chirishda ushbu qoidalarni ham tekshirish.

**Tayyorlik mezoni:** yopilgan Lead'larda bosqich va holat bir-biriga zid
bo'lmaydi.

### P1 — Mijoz va kontakt tanlashni yaxshilash

- [ ] Lead formasida faqat tanlangan mijozga tegishli kontaktlarni ko'rsatish.
- [ ] Katta mijozlar va kontaktlar ro'yxatida qidiriladigan tanlov qo'shish.
- [ ] Formadagi inglizcha maydon nomlarini o'zbekchalashtirish.

**Tayyorlik mezoni:** noto'g'ri mijoz-kontakt juftligini saqlab bo'lmaydi va
katta ro'yxatdan kerakli yozuv tez topiladi.

### P1 — Kun yakunidagi tekshiruv

- [ ] `Mijoz → Lead → Taklif → Buyurtma` oqimini brauzerda sinash.
- [ ] Tenant chegarasi, noto'g'ri qiymatlar va ruxsatlarni test qilish.
- [ ] Barcha Django va JavaScript tekshiruvlarini o'tkazish.
- [ ] Natijalarni alohida tasdiqdan keyin commit va GitHub'ga push qilish.

## Keyingi bosqichlar

### Savdo va kommunikatsiya

- [ ] Email orqali taklif yuborish va yuborilgan vaqtni qayd qilish.
- [ ] Telegram va WhatsApp uchun xavfsiz integratsiya variantini tanlash.
- [ ] Mijoz bilan barcha aloqalarni yagona timeline'da ko'rsatish.
- [ ] Follow-up vazifalarini avtomatik yaratish.

### Mahsulot va narxlar

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
