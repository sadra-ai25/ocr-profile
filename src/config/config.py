# ## src/config/config.py:
# import os
# from dotenv import load_dotenv
# from pathlib import Path
# # Load .env file
# env_path = Path('/app/.env')
# load_dotenv(dotenv_path=env_path)
# class Settings:
#     # --- Paths & IO ---
#     BASE_OUTPUT_DIR = "/app/outputs"
#     MODEL_PATH_YOLO = os.getenv("MODEL_PATH_YOLO", "/app/src/ai/weights/best.pt")
#     MODEL_DIR_REC = os.getenv("MODEL_DIR_REC", "/app/src/ai/weights/PP-OCRv5_server_rec")
#     MODEL_DIR_DET = os.getenv("MODEL_DIR_DET", "/app/src/ai/weights/PP-OCRv5_mobile_det")
#     # --- Hardware ---
#     _use_gpu_env = os.getenv("USE_GPU", "true").lower() == "true"
#     DEVICE_YOLO = 'cuda' if _use_gpu_env else 'cpu'
    
#     DEVICE_PADDLE = 'gpu' if _use_gpu_env else 'cpu'
#     # --- Processing Params ---
#     FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", 3))
#     # --- ROI Config (Variables from .env) ---
#     ROI_X = int(os.getenv("ROI_X", 2))
#     ROI_Y = int(os.getenv("ROI_Y", 432))
#     ROI_W = int(os.getenv("ROI_W", 1918))
#     ROI_H = int(os.getenv("ROI_H", 196))
#     # --- Logic Constants ---
#     HEADER_TRIGGER_COOLDOWN_FRAMES = 60
#     SILENCE_THRESHOLD_FRAMES = 25
#     # --- Network Services ---
#     RTSP_URL = os.getenv("RTSP_URL")
# # ... (سایر تنظیمات) ...
# # --- Redis Configuration ---
#     REDIS_HOST = os.getenv("REDIS_HOST", "redis")
#     REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
# settings = Settings()


import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
env_path = Path('/app/.env')
load_dotenv(dotenv_path=env_path)

class Settings:
    # --- Paths & IO ---
    BASE_OUTPUT_DIR = "/app/outputs"
    
    # مدل اول (برای پیدا کردن باکس‌های اصلی دیتادار)
    MODEL_PATH_YOLO = os.getenv("MODEL_PATH_YOLO", "/app/src/ai/weights/best.pt")
    
    # مدل دوم (جدید: برای خوانش دقیق کاراکترهای سایز، تاریخ و سریال)
    MODEL_PATH_YOLO_SIZE = os.getenv("MODEL_PATH_YOLO_SIZE", "/app/src/ai/weights/size_best.pt")
    
    # مدل‌های PaddleOCR
    MODEL_DIR_REC = os.getenv("MODEL_DIR_REC", "/app/src/ai/weights/PP-OCRv5_server_rec")
    MODEL_DIR_DET = os.getenv("MODEL_DIR_DET", "/app/src/ai/weights/PP-OCRv5_mobile_det")
    
    # --- Hardware ---
    _use_gpu_env = os.getenv("USE_GPU", "true").lower() == "true"
    DEVICE_YOLO = 'cuda' if _use_gpu_env else 'cpu'
    DEVICE_PADDLE = 'gpu' if _use_gpu_env else 'cpu'
    
    # --- Processing Params ---
    FRAME_INTERVAL = int(os.getenv("FRAME_INTERVAL", 3))
    
    # --- ROI Config (Variables from .env) ---
    ROI_X = int(os.getenv("ROI_X", 2))
    ROI_Y = int(os.getenv("ROI_Y", 432))
    ROI_W = int(os.getenv("ROI_W", 1918))
    ROI_H = int(os.getenv("ROI_H", 196))
    
    # --- Logic Constants ---
    HEADER_TRIGGER_COOLDOWN_FRAMES = int(os.getenv("HEADER_TRIGGER_COOLDOWN_FRAMES", 60))
    
    # مقدار پایه برای ثبت نهایی در صورت عدم تشخیص دیتا (بروز شده به ۳۰ بر اساس منطق جدید)
    SILENCE_THRESHOLD_FRAMES = int(os.getenv("SILENCE_THRESHOLD_FRAMES", 30))
    
    # مقدار افزایش یافته سایلنس زمانی که دیتای ما ناقص است (مثلاً سریال را خوانده اما منتظر سایز است)
    SILENCE_THRESHOLD_EXTENDED = int(os.getenv("SILENCE_THRESHOLD_EXTENDED", 90))
    
    # --- Network Services ---
    RTSP_URL = os.getenv("RTSP_URL")
    
    # --- Redis Configuration ---
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

settings = Settings()