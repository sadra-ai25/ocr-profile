from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException
import os
import time
import logging
from threading import Event, Thread
from typing import Optional
from pydantic import BaseModel
from config.config import settings
from ai.process import ProfileProcessor
from capture.producer import video_producer, camera_producer
from database.db import init_db, get_profiles

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("API")

app = FastAPI()

# Global processor instance
global_processor = ProfileProcessor()

# RTSP control variables
rtsp_stop_event = None
rtsp_producer_thread = None
rtsp_consumer_thread = None

class TimeRangeRequest(BaseModel):
    start_time: Optional[str] = None   # فرمت: YYYY-MM-DD HH:MM:SS
    end_time: Optional[str] = None     # فرمت: YYYY-MM-DD HH:MM:SS

def start_rtsp_processing(session_name: str = None):
    """
    Start RTSP/camera stream processing
    Creates a timestamp-based output folder
    """
    global rtsp_stop_event, rtsp_producer_thread, rtsp_consumer_thread

    # Prevent starting multiple times
    if rtsp_stop_event and not rtsp_stop_event.is_set():
        logger.info("⚠️ RTSP processing is already running.")
        return

    # Create output folder with timestamp (no fixed "auto_start")
    if session_name:
        safe_name = "".join(c for c in session_name if c.isalnum() or c in (' ', '-', '_')).strip()
        folder_name = safe_name or f"session_{int(time.time())}"
    else:
        folder_name = f"session_{int(time.time())}"

    output_dir = os.path.join(settings.BASE_OUTPUT_DIR, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"📂 Starting RTSP session → output directory: {output_dir}")

    # Start processor session (still passes output_dir for JSON + profile images)
    global_processor.start_session(output_dir)

    # Stop event
    rtsp_stop_event = Event()

    # Producer: camera → Redis
    rtsp_producer_thread = Thread(
        target=camera_producer,
        args=(rtsp_stop_event,),
        daemon=True
    )
    rtsp_producer_thread.start()

    # Consumer: Redis → AI processing
    rtsp_consumer_thread = Thread(
        target=global_processor.start_redis_consumer,
        daemon=True
    )
    rtsp_consumer_thread.start()

    logger.info("🚀 RTSP processing threads started.")

@app.on_event("startup")
async def startup_event():
    os.makedirs(settings.BASE_OUTPUT_DIR, exist_ok=True)
    init_db()  # Make sure DB tables exist
    logger.info(f"✅ App started. Output base folder: {settings.BASE_OUTPUT_DIR}")
    logger.info(f"✅ AI processor ready (device: {settings.DEVICE_YOLO})")

    # Automatically start RTSP/camera processing on app startup
    start_rtsp_processing()

def cleanup_file(path: str):
    """Remove temporary uploaded file"""
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"🗑️ Removed temporary file: {path}")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

def run_analysis_task(video_path: str):
    """Background task: process uploaded video file"""
    try:
        video_producer(video_path, global_processor)
    except Exception as e:
        logger.error(f"❌ Error during video analysis: {e}")
    finally:
        cleanup_file(video_path)

@app.get("/")
def read_root():
    return {
        "status": "OCR System Ready",
        "device": settings.DEVICE_YOLO
    }

@app.post("/video")
async def analyze_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload and analyze a video file (runs in background)
    """
    logger.info(f"📥 Received video upload: {file.filename}")

    ts = int(time.time())
    temp_filename = f"upload_{ts}_{file.filename}"
    temp_path = os.path.join(settings.BASE_OUTPUT_DIR, temp_filename)

    # Save uploaded file
    try:
        with open(temp_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as e:
        logger.error(f"Upload save failed: {e}")
        return {"status": "error", "message": str(e)}

    logger.info(f"File saved → queuing background processing: {temp_filename}")

    background_tasks.add_task(run_analysis_task, temp_path)

    return {
        "status": "started",
        "filename": file.filename,
        "message": "Processing started. Results (JSON + profile images) will be saved in a new folder under /outputs"
    }

@app.post("/rtsp/start")
async def start_rtsp(session_name: Optional[str] = None):
    """Manually (re)start RTSP/camera processing"""
    start_rtsp_processing(session_name)
    return {
        "status": "ok",
        "message": "RTSP processing started (or already running)."
    }

@app.post("/rtsp/stop")
async def stop_rtsp():
    """Stop the RTSP/camera processing threads"""
    global rtsp_stop_event

    if rtsp_stop_event and not rtsp_stop_event.is_set():
        rtsp_stop_event.set()
        logger.info("🛑 Stop signal sent to RTSP threads.")
        return {"status": "stopped", "message": "Stop signal sent."}
    else:
        return {"status": "idle", "message": "No RTSP processing is currently running."}

@app.post("/reports")
async def get_report_range(request: TimeRangeRequest):
    """
    Get processed profiles within a time range
    """
    try:
        logger.info(f"📊 Report requested: {request.start_time} → {request.end_time}")

        records = get_profiles(
            start_time=request.start_time,
            end_time=request.end_time
        )

        return {
            "status": "success",
            "count": len(records),
            "data": records
        }
    except Exception as e:
        logger.error(f"Database/report error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")