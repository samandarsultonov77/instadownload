import os
import re
import logging
import asyncio
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import instaloader
from instaloader.exceptions import (
    InstaloaderException,
    ConnectionException,
    LoginRequiredException,
    BadResponseException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    QueryReturnedNotFoundException,
)

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Env faylidan o'zgaruvchilarni yuklash
load_dotenv()

# Bot sozlamalari
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8523936962:AAG1NJ0UFZvYgLeDpB9yO_NgJ1TV5Ct2EXw")
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD")

# Instaloader obyekti
# Foydalanuvchi brauzer agenti (User-Agent) bloklanishning oldini olishga yordam beradi
L = instaloader.Instaloader(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Instagram tizimiga kirish (sozlash ixtiyoriy lekin bloklanmaslik uchun tavsiya etiladi)
if INSTAGRAM_USERNAME:
    try:
        # Avval local session faylni tekshiramiz
        session_file = f"session-{INSTAGRAM_USERNAME}"
        if os.path.exists(session_file):
            L.load_session_from_file(INSTAGRAM_USERNAME, filename=session_file)
            logger.info(f"Instagram session local fayldan yuklandi: {session_file}")
        else:
            try:
                # Tizimning standart joyidan yuklash
                L.load_session_from_file(INSTAGRAM_USERNAME)
                logger.info(f"Instagram session standart tizim joyidan yuklandi: {INSTAGRAM_USERNAME}")
            except FileNotFoundError:
                if INSTAGRAM_PASSWORD:
                    # Agar session topilmasa va parol berilgan bo'lsa, login qilamiz
                    L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                    L.save_session_to_file(filename=session_file)
                    logger.info(f"Instagramga kirildi va session fayli saqlandi: {session_file}")
                else:
                    logger.warning("Instagram paroli topilmadi. Session yuklanmadi.")
    except Exception as e:
        logger.error(f"Instagram hisobiga ulanishda xatolik yuz berdi: {e}")

# Instagram URL and shortcode patterns
INSTAGRAM_PATTERNS = [
    re.compile(r"instagram\.com/p/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/reel/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/reels/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/tv/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/share/reel/([A-Za-z0-9_-]+)"),
]

def extract_shortcode(url):
    """Instagram URL dan post/video shortcode ID sini ajratib olish"""
    for pattern in INSTAGRAM_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None

def fetch_post_details(shortcode):
    """
    Instaloader orqali post ma'lumotlarini olish.
    Muvaffaqiyatsiz bo'lsa, parth-dl va yt-dlp fallback tizimlaridan foydalanadi.
    Bu funksiya sinxron va asyncio.to_thread ichida ishga tushiriladi.
    """
    url = f"https://www.instagram.com/reel/{shortcode}/"
    
    # 1. Instaloader orqali urinib ko'rish
    try:
        logger.info(f"Instaloader orqali yuklab olishga urinish: {shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        return {
            "is_video": post.is_video,
            "video_url": post.video_url,
            "caption": post.caption
        }
    except Exception as instaloader_err:
        logger.warning(f"Instaloader yuklay olmadi ({type(instaloader_err).__name__}). Fallback'ka o'tilmoqda...")

        # 2. parth-dl orqali urinib ko'rish
        try:
            logger.info(f"parth-dl orqali yuklab olishga urinish: {shortcode}")
            import parth_dl
            info = parth_dl.get_info(url)
            formats = info.get("formats", [])
            video_url = None
            for fmt in formats:
                if fmt.get("type") == "video" or "video" in fmt.get("format_id", ""):
                    video_url = fmt.get("url")
                    break
            
            if video_url:
                return {
                    "is_video": True,
                    "video_url": video_url,
                    "caption": info.get("title", "")
                }
            elif info.get("images"):
                return {
                    "is_video": False,
                    "video_url": None,
                    "caption": info.get("title", "")
                }
        except Exception as parth_err:
            logger.warning(f"parth-dl ham yuklay olmadi ({type(parth_err).__name__}). yt-dlp urinib ko'rilmoqda...")

        # 3. yt-dlp orqali urinib ko'rish
        try:
            logger.info(f"yt-dlp orqali yuklab olishga urinish: {shortcode}")
            import yt_dlp
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_url = info_dict.get("url")
                if video_url:
                    return {
                        "is_video": True,
                        "video_url": video_url,
                        "caption": info_dict.get("title", "")
                    }
        except Exception as ytdlp_err:
            logger.error(f"Barcha yuklash usullari muvaffaqiyatsiz tugadi.")
        
        # Agar barchasi muvaffaqiyatsiz bo'lsa, asl xatolikni qaytaramiz
        raise instaloader_err


def download_video_file(video_url, filename):
    """
    Videoni diskka yuklab olish.
    Bu funksiya sinxron va asyncio.to_thread ichida ishga tushiriladi.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(video_url, stream=True, headers=headers, timeout=30)
    response.raise_for_status()
    with open(filename, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buyrug'iga javob"""
    welcome_text = (
        "🎥 *Instagram Video Yuklovchi Bot*\n\n"
        "Menga Instagram video/reel havolasini yuboring va men uni sizga yuklab beraman!\n\n"
        "📌 Qo'llab-quvvatlanadigan formatlar:\n"
        "• Post videolari\n"
        "• Reels\n"
        "• IGTV\n\n"
        "Faqat havolani yuboring! 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam buyrug'i"""
    help_text = (
        "📖 *Qo'llanma*\n\n"
        "1️⃣ Instagram'dan video havolasini nusxalang\n"
        "2️⃣ Ushbu botga yuboring\n"
        "3️⃣ Video yuklanib, sizga yuboriladi!\n\n"
        "💡 *Maslahatlar:*\n"
        "• Faqat ommaviy (public) postlar yuklanadi\n"
        "• Maxfiy akkauntlardan yuklab bo'lmaydi (agar tizimga ulanmagan bo'lsa)\n"
        "• Video hajmi katta bo'lsa, yuklash biroz vaqt olishi mumkin\n\n"
        "❓ Muammolar bo'lsa, /start ni bosing."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Instagram videosini yuklab yuborish"""
    url = update.message.text.strip()

    # Greeting xabarlarni tekshirish
    greetings = ["salom", "hello", "hi", "assalomu alaykum", "start", "yordam", "help", "/start", "/help"]
    if url.lower() in greetings:
        if "help" in url.lower():
            await help_command(update, context)
        else:
            await start(update, context)
        return

    # URL tekshirish
    if "instagram.com" not in url:
        await update.message.reply_text(
            "👋 Salom! Men faqat Instagram havolalari bilan ishlayman.\n\n"
            "Iltimos, Instagram post, Reels yoki IGTV havolasini yuboring! 👇"
        )
        return

    # Shortcode ajratib olish
    shortcode = extract_shortcode(url)
    if not shortcode:
        await update.message.reply_text("❌ Havoladan video/post ID sini ajratib bo'lmadi!")
        return

    # Yuklanish jarayoni haqida xabar yuborish
    status_msg = await update.message.reply_text("⏳ Video ma'lumotlari yuklanmoqda, iltimos kuting...")

    try:
        # Post ni olish (blocking chaqiruvni to_thread da bajaramiz)
        post_details = await asyncio.to_thread(fetch_post_details, shortcode)
    except ConnectionException as e:
        logger.error(f"Instagram ulanish xatoligi (IP bloklangan bo'lishi mumkin): {e}")
        await status_msg.edit_text(
            "❌ Instagram serveriga ulanishda xatolik yuz berdi.\n"
            "Katta ehtimol bilan server IP manzili vaqtinchalik bloklangan. "
            "Iltimos, birozdan so'ng qayta urinib ko'ring."
        )
        return
    except LoginRequiredException as e:
        logger.error(f"Kirish talab qilinadi: {e}")
        await status_msg.edit_text(
            "❌ Ushbu postni yuklab olish uchun tizimga kirish talab qilinadi.\n"
            "Post maxfiy (private) profilga tegishli bo'lishi mumkin."
        )
        return
    except PrivateProfileNotFollowedException as e:
        logger.error(f"Maxfiy profil: {e}")
        await status_msg.edit_text(
            "❌ Ushbu profil maxfiy (private) bo'lganligi sababli videoni yuklab bo'lmaydi."
        )
        return
    except (ProfileNotExistsException, QueryReturnedNotFoundException) as e:
        logger.error(f"Post topilmadi: {e}")
        await status_msg.edit_text(
            "❌ Havola bo'yicha post topilmadi. O'chirilgan yoki noto'g'ri bo'lishi mumkin."
        )
        return
    except BadResponseException as e:
        logger.error(f"Instagramdan noto'g'ri javob: {e}")
        await status_msg.edit_text(
            "❌ Instagram-dan noto'g'ri javob qaytdi. Havolani tekshiring."
        )
        return
    except TypeError as e:
        logger.error(f"TypeError (ehtimol Instagram bloklagan yoki login talab qilinadi): {e}")
        await status_msg.edit_text(
            "❌ Instagram so'rovni blokladi yoki kirish (login) talab qilmoqda.\n\n"
            "Sabablari:\n"
            "• Server IP-manzili Instagram tomonidan vaqtinchalik bloklangan.\n"
            "• Post maxfiy (private) akkauntga tegishli.\n"
            "• Havola noto'g'ri bo'lishi mumkin.\n\n"
            "💡 *Yechim*: Botni serverga yuklang yoki `.env` faylida Instagram login-parolini sozlang."
        )
        return
    except Exception as e:
        logger.error(f"Post olishda kutilmagan xatolik: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Xatolik yuz berdi: {str(e)}\n"
            "Iltimos, havola to'g'riligini va post ommaviyligini tekshiring."
        )
        return

    # Video ekanligini tekshirish
    if not post_details["is_video"]:
        await status_msg.edit_text("❌ Ushbu post videoni o'z ichiga olmaydi (rasm yoki karusel bo'lishi mumkin)!")
        return

    video_url = post_details["video_url"]
    if not video_url:
        await status_msg.edit_text("❌ Video yuklash havolasi topilmadi!")
        return

    # Video faylini yuklash va yuborish
    video_filename = f"video_{shortcode}.mp4"
    await status_msg.edit_text("⏳ Video yuklab olinmoqda, iltimos kuting...")

    try:
        # Videoni yuklab olish (blocking chaqiruvni to_thread da bajaramiz)
        await asyncio.to_thread(download_video_file, video_url, video_filename)

        # Fayl o'lchamini tekshirish (Telegram Bot API 50MB chekloviga ega)
        file_size = os.path.getsize(video_filename)
        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > 50:
            logger.info(f"Video o'lchami 50MB dan katta: {file_size_mb:.2f}MB. Havola yuborilmoqda.")
            await status_msg.edit_text(
                f"❌ Video o'lchami juda katta ({file_size_mb:.1f} MB).\n"
                "Telegram bot orqali faqat 50 MB gacha bo'lgan videolarni yuborish mumkin.\n\n"
                f"Siz uni quyidagi havola orqali to'g'ridan-to'g'ri yuklab olishingiz mumkin:\n🔗 [Videoni yuklab olish]({video_url})",
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            return

        # Videoni yuborish
        await status_msg.edit_text("📤 Video yuborilmoqda...")

        caption = "✅ Video yuklab olindi!\n\n"
        if post_details["caption"]:
            # Telegram sarlavha uchun max 1024 belgi qabul qiladi
            short_caption = post_details["caption"][:200]
            if len(post_details["caption"]) > 200:
                short_caption += "..."
            caption += f"📝 {short_caption}"

        with open(video_filename, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=caption,
                supports_streaming=True
            )
        await status_msg.delete()
        logger.info(f"Video muvaffaqiyatli yuborildi: {video_filename}")

    except Exception as e:
        logger.error(f"Videoni yuklash yoki yuborishda xatolik: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Videoni yuborishda xatolik yuz berdi: {str(e)}"
        )
    finally:
        # Har doim vaqtinchalik faylni o'chiramiz
        if os.path.exists(video_filename):
            try:
                os.remove(video_filename)
                logger.info(f"Vaqtinchalik fayl o'chirildi: {video_filename}")
            except Exception as e:
                logger.error(f"Vaqtinchalik faylni o'chirishda xatolik: {e}")

def main():
    """Botni ishga tushirish"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! Iltimos, uni environment variable yoki .env faylida e'lon qiling.")
        return

    # Event loop ni sozlash (Python 3.10+ va ayniqsa Python 3.14+ uchun)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Application yaratish
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlerlarni ro'yxatdan o'tkazish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    # Botni ishga tushirish
    logger.info("Bot polling rejimi bilan ishga tushirildi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
