# 🎥 Instagram Video Downloader Bot

Ushbu Telegram bot Instagram postlari, Reels va IGTV videolarini havola orqali yuklab olish uchun mo'ljallangan. 
Bot serverga yuklashga va 24/7 rejimida uzluksiz ishlashga to'liq tayyorlangan.

## 🚀 Xususiyatlari
- **Asinxron arxitektura**: Ko'p foydalanuvchilar bir vaqtning o'zida ishlatsa ham bot bloklanmaydi (`asyncio.to_thread` yordamida).
- **Avtomatik tozalash**: Server disk xotirasi to'lib qolmasligi uchun yuklab olingan videolar yuborilgach darhol avtomatik o'chiriladi.
- **Xavfsiz sozlamalar**: Bot tokenlari va maxfiy ma'lumotlar `.env` faylida saqlanadi, ochiq kodda ko'rinmaydi.
- **Instagram login va Session boshqaruvi**: Instagram sizning serveringiz IP manzilini bloklab qo'ymasligi uchun tizimga kirish va session faylini yuklash qo'llab-quvvatlanadi.
- **Hajm tekshiruvi**: Telegram Bot API cheklovi (50MB) dan katta bo'lgan videolarni aniqlab, xatolik berish o'rniga foydalanuvchiga to'g'ridan-to'g'ri yuklab olish havolasini yuboradi.

## 🛠 Mahalliy ishga tushirish (Local Run)

1. Python 3.9 yoki undan yuqori versiya o'rnatilganligiga ishonch hosil qiling.
2. Kerakli kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
3. `.env` faylini oching va bot tokeningizni kiriting.
4. Botni ishga tushiring:
   ```bash
   python main.py
   ```

## ⚙️ Environment Variables (Atrof-muhit o'zgaruvchilari)
Botni serverga joylaganda quyidagi o'zgaruvchilarni sozlash tavsiya etiladi:
- `BOT_TOKEN`: Telegram bot tokeni.
- `INSTAGRAM_USERNAME`: Instagram akkauntingiz foydalanuvchi nomi.
- `INSTAGRAM_PASSWORD`: Instagram akkauntingiz paroli.

> **Muhim tavsiya**: Agar serveringiz IP manzili Instagram tomonidan bloklansa, bot papkasida `session-<USERNAME>` nomli session fayl yaratib qo'ying yoki `INSTAGRAM_USERNAME` va `INSTAGRAM_PASSWORD` o'zgaruvchilarini bering.

## 🌐 Serverga joylash (Deployment)

### 1. Render / Railway / Heroku
Ushbu platformalarda botni juda oson ishga tushirish mumkin:
- Loyihani GitHub-ga yuklang (loyiha tarkibidagi `.gitignore` maxfiy `.env` va videolarni yuklamaydi).
- Yangi **Background Worker** (yoki Private Service) yarating.
- Platformada Environment Variables (sozlamalar) bo'limida `BOT_TOKEN` ni kiriting.
- Loyihada `Procfile` mavjudligi sababli platforma avtomatik ravishda `python main.py` buyrug'ini ishga tushiradi.

### 2. VPS (Ubuntu / Debian)
Agar o'zingizning shaxsiy VPS serveringiz bo'lsa, quyidagi buyruq yordamida botni fonda (background) ishga tushiring:
```bash
nohup python3 main.py > bot.log 2>&1 &
```
Yoki doimiy ishlashini ta'minlash uchun `systemd` service faylini yarating.
