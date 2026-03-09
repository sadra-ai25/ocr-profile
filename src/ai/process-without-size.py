import os
import cv2
import json
import numpy as np
import time
import re
import logging
from collections import Counter
from config.config import settings
import redis
import pickle
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from database.db import save_profile_data, init_db
import torch
from ultralytics import YOLO
from paddleocr import TextRecognition

logger = logging.getLogger("AI_Core")
logger.setLevel(logging.INFO)

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

class ProfileProcessor:
    def __init__(self):
        self.roi_x = settings.ROI_X
        self.roi_y = settings.ROI_Y
        self.roi_w = settings.ROI_W
        self.roi_h = settings.ROI_H
       
        init_db()
       
        self.load_models()
       
        self.reset_counters()
       
        self.output_dir = None
       
        self.session_start_time = 0
        self.total_frame_processing_time = 0
        self.processed_frame_count = 0
        self.video_fps = 25  
        self.video_total_frames = 0

    def start_redis_consumer(self, stream_name="camera_processing_tasks"):
        logger.info(f"🚀 Starting Redis consumer for stream: {stream_name}")
        redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
       
        while True:
            try:
                frames = redis_client.xread({stream_name: '0'}, block=1000, count=1)
               
                if frames:
                    stream, messages = frames[0]
                    for message_id, message_data in messages:
                        try:
                            task_message = pickle.loads(message_data[b'data'])
                            frame_id = task_message['frame_id']
                            timestamp_str = task_message['timestamp_tehran']
                           
                            produce_time = datetime.fromisoformat(timestamp_str)
                            consume_time = datetime.now(TEHRAN_TZ)
                            latency_ms = (consume_time - produce_time).total_seconds() * 1000
                           
                            frame_bytes = redis_client.get(f"frame:{frame_id}")
                            if frame_bytes is None:
                                logger.warning(f"⚠️ Frame {frame_id} not found in Redis (Expired?). Skipping.")
                                continue
                           
                            frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
                           
                            logger.info(f"📥 Dequeue Frame: {frame_id} | ⏳ Redis Latency: {latency_ms:.1f}ms")
                           
                            self.process_frame(frame, frame_id, latency_ms=latency_ms)
                           
                            redis_client.delete(f"frame:{frame_id}")
                            redis_client.xdel(stream_name, message_id)
                           
                        except Exception as inner_e:
                            logger.error(f"❌ Error processing message {message_id}: {inner_e}")
                           
            except Exception as e:
                logger.error(f"❌ Redis consumer loop error: {e}")
                time.sleep(1)

    def load_models(self):
        logger.info("🛠️ Loading AI Models (YOLO + PaddleOCR)...")
        t0 = time.time()
       
        self.det_model = YOLO(settings.MODEL_PATH_YOLO)
        logger.info(f"✅ YOLO Loaded. Device: {settings.DEVICE_YOLO}")
        
        self.rec_model = TextRecognition(model_dir=settings.MODEL_DIR_REC, device=settings.DEVICE_PADDLE)
        logger.info(f"✅ PaddleOCR Loaded. Device: {settings.DEVICE_PADDLE.upper()}")
       
        logger.info(f"⏱️ Total Load Time: {time.time() - t0:.2f}s")

    def reset_counters(self):
        self.profile_counter = 0
        self.all_profiles_data = []
       
        self.current_dates = []
        self.current_sns = []
       
        self.header_trigger_cooldown = 0
        self.silence_frame_counter = 0
        self.found_date_for_current_profile = False
       
        self.last_valid_data_frame = None
        self.last_valid_frame_number = -1
        self.active_annotation_text = None

    def start_session(self, output_directory, fps=None, total_frames=None):
        self.output_dir = output_directory
        
        self.video_fps = fps if (fps and fps > 0) else 25
        self.video_total_frames = total_frames if total_frames else 0
       
        self.session_start_time = time.time()
        self.total_frame_processing_time = 0
        self.processed_frame_count = 0
       
        self.reset_counters()
        print(f"=== START PROCESSING | ROI: {self.roi_x},{self.roi_y},{self.roi_w},{self.roi_h} ===")
        if fps:
            print(f"ℹ️ Video Info: {self.video_total_frames} frames @ {self.video_fps:.2f} FPS")

    def stop_session(self):
        self.finalize_profile("End of Stream")
       
        total_proc_time_sec = time.time() - self.session_start_time
       
        avg_frame_time_ms = 0
        if self.processed_frame_count > 0:
            avg_frame_time_ms = (self.total_frame_processing_time / self.processed_frame_count) * 1000
           
        calc_frames = self.video_total_frames if self.video_total_frames > 0 else self.processed_frame_count
        video_duration_sec = 0
        if self.video_fps > 0:
            video_duration_sec = calc_frames / self.video_fps
           
        final_summary = {
            "total_count": len(self.all_profiles_data),
            "stats": {
                "processing_time_sec": round(total_proc_time_sec, 2),
                "avg_frame_process_ms": round(avg_frame_time_ms, 1),
                "video_duration_sec": round(video_duration_sec, 2),
                "fps_used": self.video_fps
            },
            "data": self.all_profiles_data
        }
       
        if self.output_dir:
            json_path = os.path.join(self.output_dir, "final_summary.json")
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(final_summary, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f"Failed to save json: {e}")
       
        stats_msg = (
            f"\n========================================\n"
            f"📊 FINAL STATISTICS:\n"
            f"- Average time processing frame: {avg_frame_time_ms:.1f} ms\n"
            f"- Processing time: {total_proc_time_sec:.2f} s\n"
            f"- Video duration: {video_duration_sec:.2f} s\n"
            f"- Number of profiles: {len(self.all_profiles_data)}\n"
            f"========================================"
        )
       
        print(stats_msg)
        print(f"=== END PROCESSING. Total Profiles: {len(self.all_profiles_data)} ===")

    def write_log(self, msg):
        print(msg, flush=True)

    def get_most_common(self, data):
        if not data: return None
        return Counter(data).most_common(1)[0][0]

    def clean_ocr_text(self, text):
        if not text: return ""
        mapping = {'王': '1', '工': '1', '二': '2', '三': '3', '年': '7', '口': '0', '中': '4'}
        for ch, d in mapping.items():
            text = text.replace(ch, d)
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        return text.strip()

    def crop_polygon(self, image, poly):
        pts = np.array(poly, dtype=np.float32)
        if pts.shape[0] < 4: return None
        w = int(np.linalg.norm(pts[0] - pts[1]))
        h = int(np.linalg.norm(pts[1] - pts[2]))
        if w == 0 or h == 0: return None
        dst = np.array([[0,0], [w-1,0], [w-1,h-1], [0,h-1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(pts, dst)
        return cv2.warpPerspective(image, M, (w, h))

    def _draw_text_with_background(self, img, text, pos=(30, 60)):
        font = cv2.FONT_HERSHEY_DUPLEX
        scale = 1.8
        thickness = 3
        padding = 10
       
        (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
       
        x, y = pos
        pt1 = (x - padding, y - text_h - padding)
        pt2 = (x + text_w + padding, y + baseline + padding)
       
        cv2.rectangle(img, pt1, pt2, (0, 0, 0), cv2.FILLED)
        cv2.putText(img, text, pos, font, scale, (255, 255, 255), thickness)

    def finalize_profile(self, trigger):
        if (self.current_dates or self.current_sns) and self.last_valid_data_frame is not None:
            self.profile_counter += 1
           
            date_val = self.get_most_common(self.current_dates)
            sns_clean = [s for s in self.current_sns if s != "1021"]
            if not sns_clean: sns_clean = self.current_sns
            sn_val = self.get_most_common(sns_clean)
           
            d_str = date_val if date_val else "Unknown"
            s_str = sn_val if sn_val else "Unknown"
           
            formatted_date = d_str
            if len(d_str) == 8 and d_str.isdigit():
                formatted_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
           
            record = {"id": self.profile_counter, "date": formatted_date, "sn": s_str, "trigger": trigger}
            self.all_profiles_data.append(record)
           
            save_profile_data(formatted_date, s_str)
           
            self.active_annotation_text = f"Profile #{self.profile_counter} | {formatted_date} | {s_str}"
           
            save_img = self.last_valid_data_frame.copy()
            self._draw_text_with_background(save_img, self.active_annotation_text, pos=(30, 60))
           
            fname = os.path.join(self.output_dir, f"profile_{self.profile_counter}.jpg")
            # cv2.imwrite(fname, save_img)   
           
            print(f"✅ FINALIZED: {self.active_annotation_text} (Trigger: {trigger}) | Saved to: {fname}")
           
            self.current_dates = []
            self.current_sns = []
            self.found_date_for_current_profile = False
            self.last_valid_data_frame = None
            return True
           
        self.current_dates = []
        self.current_sns = []
        self.found_date_for_current_profile = False
        return False

    def process_frame(self, frame, frame_idx, latency_ms=0):
        t_start = time.time()
       
        frame_name_str = str(frame_idx)
        if isinstance(frame_idx, int):
            frame_name_str = f"{frame_idx:05d}"
       
        try:
            roi = frame[self.roi_y:self.roi_y+self.roi_h, self.roi_x:self.roi_x+self.roi_w]
        except:
            return
        display_frame = frame.copy()
       
        results = self.det_model(roi, verbose=False, device=settings.DEVICE_YOLO)
       
        polys = []
        for r in results:
            for box in r.boxes:
                b = box.xyxy[0].cpu().numpy().astype(int)
                p = np.array([
                    [b[0]+self.roi_x, b[1]+self.roi_y],
                    [b[2]+self.roi_x, b[1]+self.roi_y],
                    [b[2]+self.roi_x, b[3]+self.roi_y],
                    [b[0]+self.roi_x, b[3]+self.roi_y]
                ], dtype=np.int32)
                polys.append(p)
       
        polys = sorted(polys, key=lambda x: x[0][0])
       
        found_any_data = False
        detected_texts = []
       
        for poly in polys:
            cv2.polylines(display_frame, [poly], True, (0, 255, 0), 2)
            crop = self.crop_polygon(frame, poly)
            if crop is None: continue
           
            try:
                res = self.rec_model.predict(crop)
                raw = res[0]['rec_text'] if res else ""
                text = self.clean_ocr_text(raw)
            except: text = ""
           
            if text:
                detected_texts.append(text)
                cv2.putText(display_frame, text, (poly[0][0], poly[0][1]-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
               
                words = text.replace('.', ' ').replace(':', ' ').split()
                for w in words:
                    w_u = w.upper()
                    date_match = re.search(r'20\d{6}', w_u)
                    if date_match:
                        val = date_match.group()
                        self.current_dates.append(val)
                        self.found_date_for_current_profile = True
                        found_any_data = True
                        self.last_valid_data_frame = display_frame.copy()
                   
                    if len(w_u) == 4 and w_u.isdigit():
                        if self.found_date_for_current_profile:
                            self.current_sns.append(w_u)
                            found_any_data = True
                            self.last_valid_data_frame = display_frame.copy()
       
        full_text = " ".join(detected_texts).upper()
       
        if "FOULADYAR" in full_text:
            if self.active_annotation_text: self.active_annotation_text = None
            if self.header_trigger_cooldown == 0:
                self.finalize_profile("Header Trigger")
                self.header_trigger_cooldown = settings.HEADER_TRIGGER_COOLDOWN_FRAMES
       
        if found_any_data:
            self.silence_frame_counter = 0
        else:
            self.silence_frame_counter += 1
            if self.silence_frame_counter > settings.SILENCE_THRESHOLD_FRAMES:
                self.finalize_profile("Silence Trigger")
                self.silence_frame_counter = 0
       
        if self.header_trigger_cooldown > 0: self.header_trigger_cooldown -= 1
       
        if self.active_annotation_text:
            self._draw_text_with_background(display_frame, self.active_annotation_text, pos=(30, 60))
       
        t_end = time.time()
        dur_sec = t_end - t_start
        self.total_frame_processing_time += dur_sec
        self.processed_frame_count += 1
       
        msg = (f"Frame {frame_name_str} | Proc Time: {dur_sec*1000:.0f}ms | "
               f"Redis Latency: {latency_ms:.0f}ms | Txt: {full_text} | Device: {settings.DEVICE_YOLO}")
        self.write_log(msg)