import sqlite3
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("DB_Manager")

BASE_DIR = '/app/outputs'
DB_PATH = os.path.join(BASE_DIR, "local.db")

def get_db_connection():
    """ایجاد اتصال به دیتابیس"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """ایجاد جدول در صورت عدم وجود و بروزرسانی هوشمند اسکیما برای پشتیبانی از ستون Size"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                date TEXT,
                sn TEXT
            )
        ''')
        
        # تلاش برای اضافه کردن ستون size در صورتی که دیتابیس از قبل وجود داشته است
        try:
            cursor.execute('ALTER TABLE profiles ADD COLUMN size TEXT')
            logger.info("✅ Added 'size' column to existing DB schema.")
        except sqlite3.OperationalError:
            pass # این ستون از قبل وجود دارد و نیازی به اضافه کردن آن نیست
            
        conn.commit()
        conn.close()
        logger.info(f"✅ Database initialized at: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")

def save_profile_data(final_date, final_sn, final_size):
    """
    ذخیره داده‌های نهایی پروفایل به همراه سایز استخراج شده در دیتابیس
    """
    try:
        now_utc = datetime.utcnow()
        # تبدیل دستی به زمان ایران (UTC+3:30)
        iran_time = now_utc + timedelta(hours=3, minutes=30)
        timestamp_str = iran_time.strftime("%Y-%m-%d %H:%M:%S")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO profiles (timestamp, date, sn, size)
            VALUES (?, ?, ?, ?)
        ''', (timestamp_str, final_date, final_sn, final_size))
        conn.commit()
        conn.close()
        logger.info(f"💾 Saved to DB | Date: {final_date} | SN: {final_sn} | Size: {final_size} | Time: {timestamp_str}")
    except Exception as e:
        logger.error(f"❌ Error saving to database: {e}")

def get_profiles(start_time=None, end_time=None):
    """
    دریافت لیست پروفایل‌ها با قابلیت فیلتر زمانی دقیق روی ستون timestamp
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # اصلاح کوئری: اضافه کردن size به لیست ستون‌های انتخابی
        query = "SELECT timestamp, date, sn, size FROM profiles"
        params = []
        conditions = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
            
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        data = []
        for row in rows:
            data.append({
                "timestamp": row["timestamp"],
                "date": row["date"],
                "sn": row["sn"],
                # در صورتی که ردیف قدیمی باشد و ستون سایز نال باشد، مقدار Unknown را برمی‌گرداند
                "size": row["size"] if row["size"] else "Unknown" 
            })
            
        conn.close()
        return data
        
    except Exception as e:
        logger.error(f"❌ Error fetching profiles: {e}")
        return []