import time
import cv2
import logging
import os
import redis
import pickle
import uuid
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from config.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Capture")

redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

def video_producer(video_path, processor_instance):
    
    base_name = os.path.basename(video_path)
    clean_name = os.path.splitext(base_name)[0]
    timestamp = int(time.time())
    
    output_dir = os.path.join(settings.BASE_OUTPUT_DIR, f"{clean_name}_{timestamp}")
    
    logger.info("="*60)
    logger.info(f"🎞️ Analyzing Video: {base_name}")
    logger.info(f"📂 Output Directory: {output_dir}")
    logger.info("="*60)

    processor_instance.start_session(output_dir)

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = settings.FRAME_INTERVAL

    frame_count = 0
    processed_count = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % interval == 0:
            processor_instance.process_frame(frame, frame_count)
            processed_count += 1
            
            if processed_count % 50 == 0:
                p = (frame_count / total_frames) * 100
                logger.info(f"📊 Progress: {p:.1f}% ({frame_count}/{total_frames})")

        frame_count += 1

    cap.release()
    processor_instance.stop_session()
    logger.info(f"✅ Video Processing Completed: {output_dir}")


def camera_producer(stop_event):
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    logger.info("=" * 80)
    logger.info("🚀 Starting RTSP Camera Producer (Analysis Only Mode)...")
    rtsp_url = settings.RTSP_URL
    if not rtsp_url:
        logger.error("❌ RTSP URL is not defined in .env")
        return
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
    if not cap.isOpened():
        logger.error("❌ Failed to open RTSP stream.")
        return
    logger.info(f"✅ RTSP Connected: {rtsp_url}")
    logger.info("=" * 80)
    frame_count = 0
    stream_name = "camera_processing_tasks"
    
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            logger.warning("⚠️ Stream lost. Reconnecting...")
            cap.release()
            time.sleep(3)
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            continue
        frame_count += 1
        
        # انکود فریم برای ارسال به ردیس
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_bytes = buffer.tobytes()
        
        frame_id = str(uuid.uuid4())
        
        # ذخیره بایت‌های تصویر در ردیس با اکسپایر کوتاه
        redis_client.setex(f"frame:{frame_id}", 10, frame_bytes)
        
        # ارسال تسک به استریم ردیس با زمان دقیق تهران
        task_message = {
            'frame_id': frame_id,
            'timestamp_tehran': datetime.now(TEHRAN_TZ).isoformat()
        }
        try:
            redis_client.xadd(stream_name, {'data': pickle.dumps(task_message)}, maxlen=100)
        except Exception as e:
            logger.error(f"❌ Redis Write Error: {e}")
            
        if frame_count % 100 == 0:
            logger.debug(f"📹 Produced frame #{frame_count}")
            
    cap.release()
    logger.info("🛑 Camera Producer Stopped.")