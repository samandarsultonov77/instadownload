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
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Env faylidan o'zgaruvchilarni yuklash
load_dotenv()

from database import BotDatabase
db = BotDatabase()

# Bot sozlamalari
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8523936962:AAG1NJ0UFZvYgLeDpB9yO_NgJ1TV5Ct2EXw")
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD")

cl = Client()

if INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
    session_file = f"session_{INSTAGRAM_USERNAME}.json"
    try:
        if os.path.exists(session_file):
            cl.load_settings(session_file)
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            logger.info("Instagrapi session loaded and logged in.")
        else:
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings(session_file)
            logger.info("Instagrapi logged in and session saved.")
    except Exception as e:
        logger.error(f"Instagrapi login error: {e}")

INSTAGRAM_PATTERNS = [
    re.compile(r"instagram\.com/p/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/reel/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/reels/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/tv/([A-Za-z0-9_-]+)"),
    re.compile(r"instagram\.com/share/reel/([A-Za-z0-9_-]+)"),
]

def extract_shortcode(url):
    for pattern in INSTAGRAM_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None

def fetch_post_details(url):
    logger.info(f"Instagrapi orqali yuklashga urinish: {url}")
    try:
        media_pk = cl.media_pk_from_url(url)
        media = cl.media_info(media_pk)
        
        is_video = media.media_type == 2 or media.media_type == 8
        video_url = media.video_url
        if not video_url and getattr(media, 'resources', None):
             for res in media.resources:
                 if res.media_type == 2:
                     video_url = res.video_url
                     is_video = True
                     break
                     
        return {
            "is_video": is_video,
            "video_url": str(video_url) if video_url else None,
            "caption": media.caption_text if media.caption_text else ""
        }
    except Exception as e:
        logger.error(f"Instagrapi xatolik: {e}. Fallback yt-dlp...")
        
        try:
            import yt_dlp
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                return {
                    "is_video": True,
                    "video_url": info_dict.get("url"),
                    "caption": info_dict.get("title", "")
                }
        except Exception as ytdlp_err:
            logger.error(f"yt-dlp ham yuklay olmadi: {ytdlp_err}")
            raise e

def download_video_file(video_url, filename):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    response = requests.get(video_url, stream=True, headers=headers, timeout=60)
    response.raise_for_status()
    with open(filename, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

async def log_user_activity(update: Update):
    if update.message and update.message.from_user:
        user = update.message.from_user
        await asyncio.to_thread(
            db.log_user,
            user.id,
            user.username,
            user.first_name,
            user.last_name
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_user_activity(update)
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
    await log_user_activity(update)
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
    await log_user_activity(update)
    url = update.message.text.strip()
    greetings = ["salom", "hello", "hi", "assalomu alaykum", "start", "yordam", "help", "/start", "/help"]
    if url.lower() in greetings:
        if "help" in url.lower():
            await help_command(update, context)
        else:
            await start(update, context)
        return

    if "instagram.com" not in url:
        await update.message.reply_text(
            "👋 Salom! Men faqat Instagram havolalari bilan ishlayman.\n\n"
            "Iltimos, Instagram post, Reels yoki IGTV havolasini yuboring! 👇"
        )
        return

    shortcode = extract_shortcode(url)
    if not shortcode:
        await update.message.reply_text("❌ Havoladan video/post ID sini ajratib bo'lmadi!")
        return

    status_msg = await update.message.reply_text("⏳ Video ma'lumotlari yuklanmoqda, iltimos kuting...")

    try:
        clean_url = f"https://www.instagram.com/reel/{shortcode}/"
        post_details = await asyncio.to_thread(fetch_post_details, clean_url)
    except LoginRequired:
        await status_msg.edit_text("❌ Ushbu postni yuklab olish uchun tizimga kirish talab qilinadi. Post maxfiy bo'lishi mumkin.")
        return
    except Exception as e:
        logger.error(f"Post olishda kutilmagan xatolik: {e}")
        await status_msg.edit_text(
            "❌ Instagram-dan video ma'lumotini olish imkoni bo'lmadi.\n"
            "Sabablari: Server IP bloklangan, post o'chirilgan yoki maxfiy."
        )
        return

    if not post_details["is_video"] or not post_details.get("video_url"):
        await status_msg.edit_text("❌ Ushbu post videoni o'z ichiga olmaydi (rasm bo'lishi mumkin) yoki topilmadi!")
        return

    video_url = post_details["video_url"]
    video_filename = f"video_{shortcode}.mp4"
    await status_msg.edit_text("⏳ Video yuklab olinmoqda, iltimos kuting...")

    try:
        await asyncio.to_thread(download_video_file, video_url, video_filename)
        file_size = os.path.getsize(video_filename)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > 50:
            await status_msg.edit_text(
                f"❌ Video o'lchami juda katta ({file_size_mb:.1f} MB).\n"
                "Telegram bot orqali faqat 50 MB gacha bo'lgan videolarni yuborish mumkin.\n\n"
                f"Siz uni quyidagi havola orqali to'g'ridan-to'g'ri yuklab olishingiz mumkin:\n🔗 [Videoni yuklab olish]({video_url})",
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            return

        await status_msg.edit_text("📤 Video yuborilmoqda...")

        caption = "✅ Video yuklab olindi!\n\n"
        if post_details["caption"]:
            short_caption = post_details["caption"][:200]
            if len(post_details["caption"]) > 200:
                short_caption += "..."
            caption += f"📝 {short_caption}"

        with open(video_filename, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=caption,
                supports_streaming=True,
                write_timeout=120.0
            )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Videoni yuklash yoki yuborishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Videoni yuborishda xatolik yuz berdi: {str(e)}")
    finally:
        if os.path.exists(video_filename):
            try:
                os.remove(video_filename)
            except Exception:
                pass

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    admin_id_str = os.environ.get("ADMIN_ID")
    
    if not admin_id_str:
        await update.message.reply_text("❌ Admin ID sozlanmagan. Iltimos, .env faylida ADMIN_ID ni belgilang.")
        return
        
    try:
        admin_id = int(admin_id_str)
    except ValueError:
        await update.message.reply_text("❌ ADMIN_ID faqat sonlardan iborat bo'lishi kerak.")
        return
        
    if user_id != admin_id:
        await update.message.reply_text("⛔️ Bu buyruq faqat bot administratori uchun!")
        return
        
    stats = await asyncio.to_thread(db.get_stats)
    
    stats_text = (
        "📊 *Bot statistikasi:*\n\n"
        f"👥 *Umumiy a'zolar:* {stats['total_users']} ta\n"
        f"🔥 *Oxirgi 24 soatda faol:* {stats['active_today']} ta\n"
        f"📅 *Oxirgi 7 kunda faol:* {stats['active_week']} ta\n"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi!")
        return

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(120.0)
        .media_write_timeout(180.0)
        .pool_timeout(5.0)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    logger.info("Bot polling rejimi bilan ishga tushirildi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
