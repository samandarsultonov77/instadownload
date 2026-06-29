import os
import sqlite3
from datetime import datetime

try:
    import psycopg2
except ImportError:
    psycopg2 = None

class BotDatabase:
    def __init__(self, db_path="bot_users.db"):
        self.db_path = db_path
        self.db_url = os.environ.get("DATABASE_URL")
        
        if self.db_url:
            self.db_url = self.db_url.strip()
            if self.db_url.startswith("postgres://"):
                self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
                
        # Faqat psycopg2 o'rnatilgan bo'lsa va DATABASE_URL to'g'ri bo'lsa PostgreSQL ishlatiladi
        self.is_postgres = bool(
            psycopg2 and 
            self.db_url and 
            (self.db_url.startswith("postgresql://") or self.db_url.startswith("postgres://"))
        )
        self.init_db()

    def get_connection(self):
        """Tegishli ma'lumotlar bazasiga ulanish olish (PostgreSQL yoki SQLite)"""
        if self.is_postgres:
            try:
                return psycopg2.connect(self.db_url)
            except Exception as e:
                print(f"WARNING: PostgreSQL ulanishda xatolik yuz berdi: {e}. SQLite rejimiga o'tilmoqda...")
                self.is_postgres = False
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Ma'lumotlar bazasi va jadvalni yaratish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.is_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"ERROR: Bazani yaratishda xatolik: {e}")

    def log_user(self, user_id, username, first_name, last_name):
        """Foydalanuvchini bazaga qo'shish yoki uning oxirgi faolligini yangilash"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Foydalanuvchi bor-yo'qligini tekshirish
            query_check = "SELECT user_id FROM users WHERE user_id = %s" if self.is_postgres else "SELECT user_id FROM users WHERE user_id = ?"
            cursor.execute(query_check, (user_id,))
            user = cursor.fetchone()
            
            if user:
                # Foydalanuvchi ma'lumotlarini yangilash
                if self.is_postgres:
                    query_update = """
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s, last_activity = %s
                        WHERE user_id = %s
                    """
                else:
                    query_update = """
                        UPDATE users 
                        SET username = ?, first_name = ?, last_name = ?, last_activity = ?
                        WHERE user_id = ?
                    """
                cursor.execute(query_update, (username, first_name, last_name, now, user_id))
            else:
                # Yangi foydalanuvchi qo'shish
                if self.is_postgres:
                    query_insert = """
                        INSERT INTO users (user_id, username, first_name, last_name, joined_at, last_activity)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                else:
                    query_insert = """
                        INSERT INTO users (user_id, username, first_name, last_name, joined_at, last_activity)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """
                cursor.execute(query_insert, (user_id, username, first_name, last_name, now, now))
                
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"ERROR: log_user bajarishda xatolik: {e}")

    def get_stats(self):
        """Bot statistikalarini olish"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Umumiy foydalanuvchilar soni
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Oxirgi 24 soatdagi faol foydalanuvchilar
            if self.is_postgres:
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE last_activity >= NOW() - INTERVAL '1 day'
                """)
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE datetime(last_activity) >= datetime('now', '-1 day')
                """)
            active_today = cursor.fetchone()[0]
            
            # Oxirgi 7 kunda faol foydalanuvchilar
            if self.is_postgres:
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE last_activity >= NOW() - INTERVAL '7 days'
                """)
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE datetime(last_activity) >= datetime('now', '-7 days')
                """)
            active_week = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            return {
                "total_users": total_users,
                "active_today": active_today,
                "active_week": active_week
            }
        except Exception as e:
            print(f"ERROR: get_stats bajarishda xatolik: {e}")
            return {
                "total_users": 0,
                "active_today": 0,
                "active_week": 0
            }
