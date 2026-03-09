import sqlite3
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("DB_Manager")

## مسیر دیتابیس (در کنار همین فایل)
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = '/app/outputs'
DB_PATH = os.path.join(BASE_DIR, "local.db")

def get_db_connection():
    """ایجاد اتصال به دیتابیس"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """ایجاد جدول در صورت عدم وجود"""
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
        conn.commit()
        conn.close()
        logger.info(f"✅ Database initialized at: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")

def save_profile_data(final_date, final_sn):
    """
    ذخیره داده‌های نهایی پروفایل در دیتابیس
    """
    try:
        now_utc = datetime.utcnow()
        # تبدیل دستی به زمان ایران (UTC+3:30)
        iran_time = now_utc + timedelta(hours=3, minutes=30)
        timestamp_str = iran_time.strftime("%Y-%m-%d %H:%M:%S")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO profiles (timestamp, date, sn)
            VALUES (?, ?, ?)
        ''', (timestamp_str, final_date, final_sn))
        conn.commit()
        conn.close()
        logger.info(f"💾 Saved to DB | Date: {final_date} | SN: {final_sn} | Time: {timestamp_str}")
    except Exception as e:
        logger.error(f"❌ Error saving to database: {e}")

# def get_profiles(start_time=None, end_time=None):
#     """
#     دریافت لیست پروفایل‌ها با قابلیت فیلتر زمانی دقیق روی ستون timestamp
#     """
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         # انتخاب ستون‌ها
#         query = "SELECT date, sn FROM profiles"
#         params = []
        
#         # آرایه‌ای برای نگهداری شرط‌ها
#         conditions = []
        
#         if start_time:
#             conditions.append("timestamp >= ?")
#             params.append(start_time)
            
#         if end_time:
#             conditions.append("timestamp <= ?")
#             params.append(end_time)
        
#         # اگر شرطی وجود دارد، آن را به کوئری اضافه کن
#         if conditions:
#             query += " WHERE " + " AND ".join(conditions)
        
#         # مرتب‌سازی بر اساس زمان ثبت (جدیدترین در بالا)
#         query += " ORDER BY timestamp DESC"
        
#         cursor.execute(query, params)
#         rows = cursor.fetchall()
        
#         # تبدیل به لیست دیکشنری
#         data = []
#         for row in rows:
#             data.append({
#                 "date": row["date"],
#                 "sn": row["sn"]
#             })
            
#         conn.close()
#         return data
        
#     except Exception as e:
#         logger.error(f"❌ Error fetching profiles: {e}")
#         return []

def get_profiles(start_time=None, end_time=None):
    """
    دریافت لیست پروفایل‌ها با قابلیت فیلتر زمانی دقیق روی ستون timestamp
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # اصلاح کوئری: اضافه کردن timestamp به لیست ستون‌های انتخابی
        query = "SELECT timestamp, date, sn FROM profiles"
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
                "timestamp": row["timestamp"], # ✅ حالا این ستون هم برمی‌گردد
                "date": row["date"],
                "sn": row["sn"]
            })
            
        conn.close()
        return data
        
    except Exception as e:
        logger.error(f"❌ Error fetching profiles: {e}")
        return []