# import os
# import cv2
# import json
# import numpy as np
# import time
# import re
# import logging
# import difflib
# from collections import Counter
# from config.config import settings
# import redis
# import pickle
# from zoneinfo import ZoneInfo
# from datetime import datetime, timezone
# from database.db import save_profile_data, init_db

# # --- IMPORT YOLO ---
# import torch
# from ultralytics import YOLO
# from paddleocr import TextRecognition

# # تنظیم لاگر مخصوص این ماژول
# logger = logging.getLogger("AI_Core")
# logger.setLevel(logging.INFO)

# # منطقه زمانی تهران برای محاسبات دقیق
# TEHRAN_TZ = ZoneInfo("Asia/Tehran")

# class ProfileProcessor:
#     def __init__(self):
#         """بارگذاری مدل‌ها هنگام ساخته شدن کلاس"""
#         self.roi_x = settings.ROI_X
#         self.roi_y = settings.ROI_Y
#         self.roi_w = settings.ROI_W
#         self.roi_h = settings.ROI_H
       
#         # اطمینان از ساخته شدن و بروزرسانی جدول دیتابیس هنگام شروع
#         init_db()
       
#         # بارگذاری مدل‌ها
#         self.load_models()
       
#         # متغیرهای داخلی
#         self.reset_counters()
       
#         # متغیرهای مدیریت فایل و آمار
#         self.output_dir = None
       
#         # متغیرهای آمار زمانی
#         self.session_start_time = 0
#         self.total_frame_processing_time = 0
#         self.processed_frame_count = 0
#         self.video_fps = 25  # مقدار پیش‌فرض
#         self.video_total_frames = 0

#     def is_group_like(self, text):
#         """Fuzzy detection for GROUP-like"""
#         if not text: return False
#         t = re.sub(r'[^A-Z0-9*]', '', text.upper())
#         variants = ['GROUP', 'BROUP', '6ROUP', 'GROLP', 'GR0UP', 'GROU P', 'BROU P', 
#                     'GROHP', 'SROUP', 'BROLP', 'ROLP', 'GROU', 'GROUPP', 'GROUF']
#         for v in variants:
#             v_clean = re.sub(r'[^A-Z0-9*]', '', v.upper())
#             if v_clean in t or difflib.SequenceMatcher(None, t, v_clean).ratio() > 0.68:
#                 return True
#         return False

#     def normalize_size_candidate(self, candidate):
#         """STRICT normalization to 'XX*XX' format."""
#         clean = re.sub(r'[^0-9*]', '', candidate)
#         match = re.search(r'(\d{1,2})\*?(\d{1,2})', clean)
#         if match:
#             left = match.group(1).zfill(2)
#             right = match.group(2).zfill(2)
#             return f"{left}*{right}"
#         if len(clean) == 4 and clean.isdigit():
#             return f"{clean[:2]}*{clean[2:]}"
#         if len(clean) == 5 and clean[2] == '*':
#             return f"{clean[:2]}*{clean[3:]}"
#         return None

#     def start_redis_consumer(self, stream_name="camera_processing_tasks"):
#         logger.info(f"🚀 Starting Redis consumer for stream: {stream_name}")
#         redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
       
#         while True:
#             try:
#                 frames = redis_client.xread({stream_name: '0'}, block=1000, count=1)
               
#                 if frames:
#                     stream, messages = frames[0]
#                     for message_id, message_data in messages:
#                         try:
#                             task_message = pickle.loads(message_data[b'data'])
#                             frame_id = task_message['frame_id']
#                             timestamp_str = task_message['timestamp_tehran']
                           
#                             produce_time = datetime.fromisoformat(timestamp_str)
#                             consume_time = datetime.now(TEHRAN_TZ)
#                             latency_ms = (consume_time - produce_time).total_seconds() * 1000
                           
#                             frame_bytes = redis_client.get(f"frame:{frame_id}")
#                             if frame_bytes is None:
#                                 logger.warning(f"⚠️ Frame {frame_id} not found in Redis (Expired?). Skipping.")
#                                 continue
                           
#                             frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
                           
#                             logger.info(f"📥 Dequeue Frame: {frame_id} | ⏳ Redis Latency: {latency_ms:.1f}ms")
                           
#                             self.process_frame(frame, frame_id, latency_ms=latency_ms)
                           
#                             redis_client.delete(f"frame:{frame_id}")
#                             redis_client.xdel(stream_name, message_id)
                           
#                         except Exception as inner_e:
#                             logger.error(f"❌ Error processing message {message_id}: {inner_e}")
                           
#             except Exception as e:
#                 logger.error(f"❌ Redis consumer loop error: {e}")
#                 time.sleep(1)

#     def load_models(self):
#         logger.info("🛠️ Loading AI Models (YOLO + PaddleOCR)...")
#         t0 = time.time()
       
#         self.det_model = YOLO(settings.MODEL_PATH_YOLO)
#         logger.info(f"✅ YOLO Loaded. Device: {settings.DEVICE_YOLO}")
        
#         # بارگذاری مدل یولوی دوم برای خوانش دقیق‌تر کاراکترهای سایز، سریال و تاریخ
#         # از متغیر محیطی MODEL_PATH_YOLO_SIZE استفاده می‌کند و در صورت نبود به مسیر دیفالت ارجاع می‌دهد
#         size_model_path = os.getenv("MODEL_PATH_YOLO_SIZE", "/app/src/ai/weights/size_best.pt")
#         try:
#             self.size_det_model = YOLO(size_model_path)
#             logger.info(f"✅ YOLO Size/Data Model Loaded from {size_model_path}. Device: {settings.DEVICE_YOLO}")
#         except Exception as e:
#             logger.error(f"❌ Failed to load Size Model! Ensure path is correct: {e}")
#             self.size_det_model = None
        
#         self.rec_model = TextRecognition(model_dir=settings.MODEL_DIR_REC, device=settings.DEVICE_PADDLE)
#         logger.info(f"✅ PaddleOCR Loaded. Device: {settings.DEVICE_PADDLE.upper()}")
       
#         logger.info(f"⏱️ Total Load Time: {time.time() - t0:.2f}s")

#     def reset_counters(self):
#         self.profile_counter = 0
#         self.all_profiles_data = []
       
#         self.current_dates = []
#         self.current_sns = []
#         self.current_sizes = []
       
#         self.header_trigger_cooldown = 0
#         self.silence_frame_counter = 0
#         self.found_date_for_current_profile = False
       
#         self.last_valid_data_frame = None
#         self.last_valid_frame_number = -1
#         self.active_annotation_text = None

#     def start_session(self, output_directory, fps=None, total_frames=None):
#         self.output_dir = output_directory
        
#         self.video_fps = fps if (fps and fps > 0) else 25
#         self.video_total_frames = total_frames if total_frames else 0
       
#         self.session_start_time = time.time()
#         self.total_frame_processing_time = 0
#         self.processed_frame_count = 0
       
#         self.reset_counters()
#         print(f"=== START PROCESSING | ROI: {self.roi_x},{self.roi_y},{self.roi_w},{self.roi_h} ===")
#         if fps:
#             print(f"ℹ️ Video Info: {self.video_total_frames} frames @ {self.video_fps:.2f} FPS")

#     def stop_session(self):
#         self.finalize_profile("End of Stream")
       
#         total_proc_time_sec = time.time() - self.session_start_time
       
#         avg_frame_time_ms = 0
#         if self.processed_frame_count > 0:
#             avg_frame_time_ms = (self.total_frame_processing_time / self.processed_frame_count) * 1000
           
#         calc_frames = self.video_total_frames if self.video_total_frames > 0 else self.processed_frame_count
#         video_duration_sec = 0
#         if self.video_fps > 0:
#             video_duration_sec = calc_frames / self.video_fps
           
#         final_summary = {
#             "total_count": len(self.all_profiles_data),
#             "stats": {
#                 "processing_time_sec": round(total_proc_time_sec, 2),
#                 "avg_frame_process_ms": round(avg_frame_time_ms, 1),
#                 "video_duration_sec": round(video_duration_sec, 2),
#                 "fps_used": self.video_fps
#             },
#             "data": self.all_profiles_data
#         }
       
#         if self.output_dir:
#             json_path = os.path.join(self.output_dir, "final_summary.json")
#             try:
#                 with open(json_path, 'w', encoding='utf-8') as f:
#                     json.dump(final_summary, f, ensure_ascii=False, indent=4)
#             except Exception as e:
#                 logger.error(f"Failed to save json: {e}")
       
#         stats_msg = (
#             f"\n========================================\n"
#             f"📊 FINAL STATISTICS:\n"
#             f"- Average time processing frame: {avg_frame_time_ms:.1f} ms\n"
#             f"- Processing time: {total_proc_time_sec:.2f} s\n"
#             f"- Video duration: {video_duration_sec:.2f} s\n"
#             f"- Number of profiles: {len(self.all_profiles_data)}\n"
#             f"========================================"
#         )
       
#         print(stats_msg)
#         print(f"=== END PROCESSING. Total Profiles: {len(self.all_profiles_data)} ===")

#     def write_log(self, msg):
#         print(msg, flush=True)

#     def get_most_common(self, data):
#         if not data: return None
#         return Counter(data).most_common(1)[0][0]

#     def clean_ocr_text(self, text):
#         if not text: return ""
#         mapping = {'王': '1', '工': '1', '二': '2', '三': '3', '年': '7', '口': '0', '中': '4'}
#         for ch, d in mapping.items():
#             text = text.replace(ch, d)
#         text = re.sub(r'[^\x00-\x7F]+', '', text)
#         return text.strip()

#     def crop_polygon(self, image, poly):
#         pts = np.array(poly, dtype=np.float32)
#         if pts.shape[0] < 4: return None
#         w = int(np.linalg.norm(pts[0] - pts[1]))
#         h = int(np.linalg.norm(pts[1] - pts[2]))
#         if w == 0 or h == 0: return None
#         dst = np.array([[0,0], [w-1,0], [w-1,h-1], [0,h-1]], dtype=np.float32)
#         M = cv2.getPerspectiveTransform(pts, dst)
#         return cv2.warpPerspective(image, M, (w, h))

#     def _draw_text_with_background(self, img, text, pos=(30, 60)):
#         font = cv2.FONT_HERSHEY_DUPLEX
#         scale = 1.2
#         thickness = 2
#         padding = 10
       
#         (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
       
#         x, y = pos
#         pt1 = (x - padding, y - text_h - padding)
#         pt2 = (x + text_w + padding, y + baseline + padding)
       
#         cv2.rectangle(img, pt1, pt2, (0, 0, 0), cv2.FILLED)
#         cv2.putText(img, text, pos, font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

#     def finalize_profile(self, trigger):
#         if (self.current_dates or self.current_sns or self.current_sizes) and self.last_valid_data_frame is not None:
#             self.profile_counter += 1
           
#             date_val = self.get_most_common(self.current_dates)
#             sns_clean = [s for s in self.current_sns if s != "1021"]
#             if not sns_clean: sns_clean = self.current_sns
#             sn_val = self.get_most_common(sns_clean)
#             size_val = self.get_most_common(self.current_sizes)
           
#             d_str = date_val if date_val else "Unknown"
#             s_str = sn_val if sn_val else "Unknown"
#             size_str = size_val if size_val else "Unknown"
           
#             formatted_date = d_str
#             if len(d_str) == 8 and d_str.isdigit():
#                 formatted_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
           
#             record = {"id": self.profile_counter, "date": formatted_date, "sn": s_str, "size": size_str, "trigger": trigger}
#             self.all_profiles_data.append(record)
           
#             save_profile_data(formatted_date, s_str, size_str)
           
#             self.active_annotation_text = f"Profile #{self.profile_counter} | {formatted_date} | SN: {s_str} | Size: {size_str}"
           
#             save_img = self.last_valid_data_frame.copy()
#             self._draw_text_with_background(save_img, self.active_annotation_text, pos=(30, 60))
           
#             # fname = os.path.join(self.output_dir, f"profile_{self.profile_counter}.jpg")
#             # cv2.imwrite(fname, save_img)   
           
#             print(f"✅ FINALIZED: {self.active_annotation_text} (Trigger: {trigger})")
           
#             self.current_dates.clear()
#             self.current_sns.clear()
#             self.current_sizes.clear()
#             self.found_date_for_current_profile = False
#             self.last_valid_data_frame = None
#             return True
           
#         self.current_dates.clear()
#         self.current_sns.clear()
#         self.current_sizes.clear()
#         self.found_date_for_current_profile = False
#         return False

#     def process_frame(self, frame, frame_idx, latency_ms=0):
#         t_start = time.time()
       
#         frame_name_str = str(frame_idx)
#         if isinstance(frame_idx, int):
#             frame_name_str = f"{frame_idx:05d}"
       
#         try:
#             roi = frame[self.roi_y:self.roi_y+self.roi_h, self.roi_x:self.roi_x+self.roi_w]
#         except:
#             return
            
#         display_frame = frame.copy()
#         results = self.det_model(roi, verbose=False, device=settings.DEVICE_YOLO)
       
#         polys = []
#         for r in results:
#             for box in r.boxes:
#                 b = box.xyxy[0].cpu().numpy().astype(int)
#                 p = np.array([
#                     [b[0]+self.roi_x, b[1]+self.roi_y],
#                     [b[2]+self.roi_x, b[1]+self.roi_y],
#                     [b[2]+self.roi_x, b[3]+self.roi_y],
#                     [b[0]+self.roi_x, b[3]+self.roi_y]
#                 ], dtype=np.int32)
#                 polys.append(p)
       
#         polys = sorted(polys, key=lambda x: x[0][0])
       
#         found_data_this_frame = False
#         final_results = []
       
#         # 1. اجرای یولوی پایه و PaddleOCR برای پیدا کردن باکس‌های دیتادار اولیه
#         for poly in polys:
#             cv2.polylines(display_frame, [poly], True, (0, 255, 0), 2)
#             crop = self.crop_polygon(frame, poly)
#             if crop is None: continue
           
#             try:
#                 res = self.rec_model.predict(crop)
#                 raw = res[0]['rec_text'] if res else ""
#                 text = self.clean_ocr_text(raw)
#             except: text = ""
           
#             if text:
#                 cv2.putText(display_frame, text, (poly[0][0], poly[0][1]-10),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
#                 final_results.append({"text": text, "bounding_box": poly})
               
#         concatenated_text = " ".join([r['text'] for r in final_results])
#         full_text = concatenated_text.upper()
       
#         # --- HEADER DETECTION ---
#         if "FOULADYAR" in full_text:
#             if self.active_annotation_text: self.active_annotation_text = None
#             if self.header_trigger_cooldown == 0:
#                 self.finalize_profile("Header Trigger")
#                 self.header_trigger_cooldown = settings.HEADER_TRIGGER_COOLDOWN_FRAMES
#                 self.silence_frame_counter = 0

#         # --- COMBINED DATA & SIZE EXTRACTION ---
#         for idx, item in enumerate(final_results):
#             paddle_text = item['text']
#             paddle_text_up = paddle_text.upper()

#             # --- 1. SIZE DETECTION LOGIC ---
#             if self.is_group_like(paddle_text):
#                 if idx + 1 < len(final_results):
#                     next_box = final_results[idx + 1]['bounding_box']
#                     next_crop = self.crop_polygon(frame, next_box)

#                     if next_crop is not None and getattr(self, "size_det_model", None):
#                         size_res = self.size_det_model(next_crop, verbose=False, device=settings.DEVICE_YOLO, conf=0.6, iou=0.45)
#                         chars = []
#                         for r in size_res:
#                             for box in r.boxes:
#                                 cls_id = int(box.cls[0])
#                                 class_name = self.size_det_model.names[cls_id]
#                                 bb = box.xyxy[0].cpu().numpy().astype(int)
#                                 ch_clean = re.sub(r'[^A-Z0-9*]', '', class_name.upper())
#                                 if ch_clean:
#                                     cx = (bb[0] + bb[2]) / 2.0
#                                     chars.append((cx, ch_clean))

#                         if chars:
#                             sorted_chars = [c for _, c in sorted(chars, key=lambda x: x[0])]
#                             raw_candidate = ''.join(sorted_chars)
#                             normalized = self.normalize_size_candidate(raw_candidate)
                            
#                             if normalized:
#                                 weight = 5 if ('*' in raw_candidate and len(raw_candidate) >= 5) else 1
#                                 self.current_sizes.extend([normalized] * weight)
#                                 found_data_this_frame = True
#                                 self.last_valid_data_frame = display_frame.copy()
#                                 continue  

#                         # Fallback PaddleOCR for Size
#                         try:
#                             fallback_out = self.rec_model.predict(next_crop)
#                             if fallback_out:
#                                 fallback_text = fallback_out[0]['rec_text'] if isinstance(fallback_out[0], dict) else fallback_out[0][0]
#                                 fallback_clean = re.sub(r'[^0-9*]', '', fallback_text)
#                                 normalized = self.normalize_size_candidate(fallback_clean)
#                                 if normalized:
#                                     weight = 5 if ('*' in fallback_clean and len(fallback_clean) >= 5) else 1
#                                     self.current_sizes.extend([normalized] * weight)
#                                     found_data_this_frame = True
#                                     self.last_valid_data_frame = display_frame.copy()
#                         except:
#                             pass
#                 continue

#             # --- 2. DATE & SN DETECTION LOGIC ---
#             digits_only = re.sub(r'\D', '', paddle_text_up)
#             if len(paddle_text_up) >= 8 and len(digits_only) >= 6:
#                 if re.search(r'(0202|202\d|10202|ST0|8T0|S10|AST)', paddle_text_up):
#                     date_crop = self.crop_polygon(frame, item['bounding_box'])
#                     if date_crop is None or not getattr(self, "size_det_model", None): continue

#                     date_res = self.size_det_model(date_crop, verbose=False, device=settings.DEVICE_YOLO, conf=0.5, iou=0.45)
#                     d_chars = []
#                     for dr in date_res:
#                         for d_box in dr.boxes:
#                             d_cls_id = int(d_box.cls[0])
#                             d_name = self.size_det_model.names[d_cls_id]
#                             d_ch = re.sub(r'[^A-Z0-9]', '', d_name.upper())
#                             if d_ch:
#                                 dbb = d_box.xyxy[0].cpu().numpy()
#                                 d_chars.append(( (dbb[0]+dbb[2])/2.0, d_ch ))
                                
#                     d_sorted = sorted(d_chars, key=lambda x: x[0])
#                     yolo_date_raw = ''.join([c[1] for c in d_sorted])
                    
#                     final_date = None
#                     m_date = re.search(r'(20\d{6})', yolo_date_raw)
#                     if m_date:
#                         final_date = m_date.group(1)
#                     else:
#                         if len(yolo_date_raw) >= 11:
#                             ignored_prefix_date = yolo_date_raw[3:]
#                             m_sliced = re.search(r'^(\d{8})', ignored_prefix_date)
#                             if m_sliced:
#                                 final_date = m_sliced.group(1)

#                     if final_date:
#                         self.current_dates.append(final_date)
#                         self.found_date_for_current_profile = True
#                         found_data_this_frame = True
#                         self.last_valid_data_frame = display_frame.copy()
                        
#                         # Process SN (Next Box)
#                         if idx + 1 < len(final_results):
#                             sn_item = final_results[idx + 1]
#                             sn_text_up = sn_item['text'].upper()
                            
#                             if not self.is_group_like(sn_text_up):
#                                 sn_crop = self.crop_polygon(frame, sn_item['bounding_box'])
#                                 if sn_crop is not None:
#                                     sn_res = self.size_det_model(sn_crop, verbose=False, device=settings.DEVICE_YOLO, conf=0.5, iou=0.45)
#                                     s_chars = []
#                                     for sr in sn_res:
#                                         for s_box in sr.boxes:
#                                             s_cls = int(s_box.cls[0])
#                                             s_cname = self.size_det_model.names[s_cls]
#                                             s_ch = re.sub(r'[^A-Z0-9]', '', s_cname.upper())
#                                             if s_ch:
#                                                 sbb = s_box.xyxy[0].cpu().numpy()
#                                                 s_chars.append(( (sbb[0]+sbb[2])/2.0, s_ch ))
                                    
#                                     s_sorted = sorted(s_chars, key=lambda x: x[0])
#                                     yolo_sn_raw = ''.join([c[1] for c in s_sorted])
                                    
#                                     sn_digits = re.sub(r'\D', '', yolo_sn_raw)
#                                     if len(sn_digits) == 4:
#                                         self.current_sns.append(sn_digits)
#                                         found_data_this_frame = True
#                                         self.last_valid_data_frame = display_frame.copy()
#                                     else:
#                                         m_sn_bound = re.search(r'\b(\d{4})\b', yolo_sn_raw)
#                                         m_sn_cons = re.search(r'(\d{4})', yolo_sn_raw)
#                                         best_sn = m_sn_bound.group(1) if m_sn_bound else (m_sn_cons.group(1) if m_sn_cons else None)
#                                         if best_sn:
#                                             self.current_sns.append(best_sn)
#                                             found_data_this_frame = True
#                                             self.last_valid_data_frame = display_frame.copy()

#         # --- SMART SILENCE LOGIC ---
#         if not found_data_this_frame:
#             self.silence_frame_counter += 1
            
#             has_identity = (len(self.current_dates) > 0) or (len(self.current_sns) > 0)
#             has_size = (len(self.current_sizes) > 0)
            
#             silence_threshold_extended = getattr(settings, 'SILENCE_THRESHOLD_EXTENDED', 90)
            
#             if (has_identity and not has_size) or (has_size and not has_identity):
#                 current_threshold = silence_threshold_extended
#             else:
#                 current_threshold = settings.SILENCE_THRESHOLD_FRAMES

#             if self.silence_frame_counter > current_threshold:
#                 if self.current_dates or self.current_sns or self.current_sizes:
#                     self.finalize_profile(f"Silence Trigger (Limit: {current_threshold})")
#                 self.silence_frame_counter = 0
#         else:
#             self.silence_frame_counter = 0

#         if self.header_trigger_cooldown > 0: self.header_trigger_cooldown -= 1
       
#         if self.active_annotation_text:
#             self._draw_text_with_background(display_frame, self.active_annotation_text, pos=(30, 60))
       
#         t_end = time.time()
#         dur_sec = t_end - t_start
#         self.total_frame_processing_time += dur_sec
#         self.processed_frame_count += 1
       
#         msg = (f"Frame {frame_name_str} | Proc Time: {dur_sec*1000:.0f}ms | "
#                f"Redis Latency: {latency_ms:.0f}ms | Txt: {full_text} | Device: {settings.DEVICE_YOLO}")
#         self.write_log(msg)



##=======================================================================================================================
## PaddleOCR: Acts as an explorer, locating text and reading it generally (e.g., detecting headers or "GROUP").
## YOLO Model 2: this model processes and read fine characters of (Date, SN, Size)
import os
import cv2
import json
import numpy as np
import time
import re
import logging
import difflib
from collections import Counter
from config.config import settings
import redis
import pickle
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from database.db import save_profile_data, init_db

# --- IMPORT YOLO ---
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

    def is_group_like(self, text):
        """Fuzzy detection for GROUP-like"""
        if not text: return False
        t = re.sub(r'[^A-Z0-9*]', '', text.upper())
        variants =['GROUP', 'BROUP', '6ROUP', 'GROLP', 'GR0UP', 'GROU P', 'BROU P', 
                    'GROHP', 'SROUP', 'BROLP', 'ROLP', 'GROU', 'GROUPP', 'GROUF']
        for v in variants:
            v_clean = re.sub(r'[^A-Z0-9*]', '', v.upper())
            if v_clean in t or difflib.SequenceMatcher(None, t, v_clean).ratio() > 0.68:
                return True
        return False

    def normalize_size_candidate(self, candidate):
        """STRICT normalization to 'XX*XX' format."""
        clean = re.sub(r'[^0-9*]', '', candidate)
        match = re.search(r'(\d{1,2})\*?(\d{1,2})', clean)
        if match:
            left = match.group(1).zfill(2)
            right = match.group(2).zfill(2)
            return f"{left}*{right}"
        if len(clean) == 4 and clean.isdigit():
            return f"{clean[:2]}*{clean[2:]}"
        if len(clean) == 5 and clean[2] == '*':
            return f"{clean[:2]}*{clean[3:]}"
        return None

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
        
        size_model_path = getattr(settings, "MODEL_PATH_YOLO_SIZE", "/app/src/ai/weights/size_best.pt")
        try:
            self.size_det_model = YOLO(size_model_path)
            logger.info(f"✅ YOLO Size/Data Model Loaded from {size_model_path}. Device: {settings.DEVICE_YOLO}")
        except Exception as e:
            logger.error(f"❌ Failed to load Size Model! Ensure path is correct: {e}")
            self.size_det_model = None
        
        self.rec_model = TextRecognition(model_dir=settings.MODEL_DIR_REC, device=settings.DEVICE_PADDLE)
        logger.info(f"✅ PaddleOCR Loaded. Device: {settings.DEVICE_PADDLE.upper()}")
       
        logger.info(f"⏱️ Total Load Time: {time.time() - t0:.2f}s")

    def reset_counters(self):
        self.profile_counter = 0
        self.all_profiles_data =[]
       
        self.current_dates = []
        self.current_sns =[]
        self.current_sizes =[]
       
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
        """Cleans OCR text (still useful for display text mapping)"""
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
        dst = np.array([[0,0], [w-1,0], [w-1,h-1],[0,h-1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(pts, dst)
        return cv2.warpPerspective(image, M, (w, h))

    def _draw_text_with_background(self, img, text, pos=(30, 60)):
        font = cv2.FONT_HERSHEY_DUPLEX
        scale = 1.2
        thickness = 2
        padding = 10
       
        (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
       
        x, y = pos
        pt1 = (x - padding, y - text_h - padding)
        pt2 = (x + text_w + padding, y + baseline + padding)
       
        cv2.rectangle(img, pt1, pt2, (0, 0, 0), cv2.FILLED)
        cv2.putText(img, text, pos, font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    def finalize_profile(self, trigger):
        if (self.current_dates or self.current_sns or self.current_sizes) and self.last_valid_data_frame is not None:
            self.profile_counter += 1
           
            date_val = self.get_most_common(self.current_dates)
            
            # Safe SN filtering mechanism if an SN misread happens to just be a common DIN component.
            clean_sn_list = [s for s in self.current_sns if s not in["1021", "2021", "1020", "2022", "1821", "0881"]]
            if not clean_sn_list and self.current_sns: 
                clean_sn_list = self.current_sns
                
            sn_val = self.get_most_common(clean_sn_list)
            size_val = self.get_most_common(self.current_sizes) if self.current_sizes else "Unknown"
           
            d_str = date_val if date_val else "Unknown"
            s_str = sn_val if sn_val else "Unknown"
            size_str = size_val
           
            formatted_date = d_str
            if len(d_str) == 8 and d_str.isdigit():
                formatted_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
           
            record = {"id": self.profile_counter, "date": formatted_date, "sn": s_str, "size": size_str, "trigger": trigger}
            self.all_profiles_data.append(record)
           
            save_profile_data(formatted_date, s_str, size_str)
           
            self.active_annotation_text = f"Profile #{self.profile_counter} | {formatted_date} | SN: {s_str} | Size: {size_str}"
           
            save_img = self.last_valid_data_frame.copy()
            self._draw_text_with_background(save_img, self.active_annotation_text, pos=(30, 60))
           
            # fname = os.path.join(self.output_dir, f"profile_{self.profile_counter}.jpg")
            # cv2.imwrite(fname, save_img)   
           
            logger.info("\n" + "="*60)
            logger.info(f"✅ PROFILE #{self.profile_counter} FINALIZED ({trigger})")
            logger.info(f"   Date : {formatted_date}")
            logger.info(f"   SN   : {s_str}")
            logger.info(f"   Size : {size_str}")
            logger.info("="*60 + "\n")
           
            self.current_dates.clear()
            self.current_sns.clear()
            self.current_sizes.clear()
            self.found_date_for_current_profile = False
            self.last_valid_data_frame = None
            self.last_valid_frame_number = -1
            return True
           
        self.current_dates.clear()
        self.current_sns.clear()
        self.current_sizes.clear()
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
       
        polys =[]
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
       
        found_data_this_frame = False
        final_results =[]
       
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
                cv2.putText(display_frame, text, (poly[0][0], poly[0][1]-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                final_results.append({"text": text, "bounding_box": poly})
               
        concatenated_text = " ".join([r['text'] for r in final_results])
        full_text = concatenated_text.upper()
       
        # --- HEADER DETECTION ---
        if "FOULADYAR" in full_text:
            if self.active_annotation_text: 
                self.write_log(" → Header detected → sticky annotation removed")
                self.active_annotation_text = None
            if self.header_trigger_cooldown == 0:
                self.finalize_profile("Header Trigger")
                self.header_trigger_cooldown = settings.HEADER_TRIGGER_COOLDOWN_FRAMES
                self.silence_frame_counter = 0

        # --- COMBINED DATA & SIZE EXTRACTION ---
        for idx, item in enumerate(final_results):
            paddle_text = item['text']
            paddle_text_up = paddle_text.upper()
            digits_only = re.sub(r'\D', '', paddle_text_up)

            # ----------------------------------------------------
            # PADDLE NATIVE DATA FALLBACK (Globally extracted if present directly)
            # Prevents YOLO misreads/skips, fixes combined date+sn and sn typos.
            # ----------------------------------------------------

            # Date Extract Native Fallback
            m_d_pad = re.search(r'(202[0-9]{5})', paddle_text_up)
            if m_d_pad:
                self.current_dates.append(m_d_pad.group(1))
                found_data_this_frame = True
                self.last_valid_data_frame = display_frame.copy()
                self.last_valid_frame_number = frame_idx

            elif "26022" in digits_only:
                m_dp = re.search(r'(2602\d{2})', digits_only)
                if m_dp:
                    d_cand = f"20{m_dp.group(1)}"
                    self.current_dates.append(d_cand)
                    found_data_this_frame = True
                    self.last_valid_data_frame = display_frame.copy()
                    self.last_valid_frame_number = frame_idx

            # Size Extract Native Fallback (Searches for dimensions strictly anywhere in text like 40*20)
            m_sz = re.search(r'(\d{1,2})\s*[*xX]\s*(\d{1,2})', paddle_text_up)
            if m_sz:
                raw_sz = f"{m_sz.group(1)}*{m_sz.group(2)}"
                norm_sz = self.normalize_size_candidate(raw_sz)
                if norm_sz:
                    self.current_sizes.extend([norm_sz] * 2) # Extra weight because paddle read directly is powerful
                    found_data_this_frame = True
                    self.last_valid_data_frame = display_frame.copy()
                    self.last_valid_frame_number = frame_idx

            # SN Extract Native Fallback (Stand-alone EXACT 4-digits) -> Overrules bad 6543 overlapping.
            sn_matches = re.findall(r'(?<!\d)(\d{4})(?!\d)', paddle_text_up)
            for s_cand in sn_matches:
                # Exclude code noise usually appended in tubes
                if s_cand not in["1021", "2021", "1020", "2022", "1821", "2821", "0881", "2029", "8000"]:
                    self.current_sns.extend([s_cand] * 3) # Extremely high weight, preventing YOLO mistakes (like 6543 vs 6534)
                    found_data_this_frame = True
                    self.last_valid_data_frame = display_frame.copy()
                    self.last_valid_frame_number = frame_idx


            # ----------------------------------------------------
            # 1. SIZE DETECTION LOGIC (Using secondary YOLO)
            # ----------------------------------------------------
            if self.is_group_like(paddle_text):
                self.write_log(f" → GROUP-like detected: '{paddle_text}' (idx={idx})")
                
                if idx + 1 < len(final_results):
                    next_box = final_results[idx + 1]['bounding_box']
                    next_crop = self.crop_polygon(frame, next_box)

                    if next_crop is not None and getattr(self, "size_det_model", None):
                        size_res = self.size_det_model(next_crop, verbose=False, device=settings.DEVICE_YOLO, conf=0.6, iou=0.45)
                        chars =[]
                        num_boxes = len(size_res[0].boxes) if size_res else 0
                        self.write_log(f"    YOLO Size → {num_boxes} boxes (using CLASS NAMES)")
                        
                        for r in size_res:
                            for box in r.boxes:
                                cls_id = int(box.cls[0])
                                class_name = self.size_det_model.names[cls_id]
                                bb = box.xyxy[0].cpu().numpy().astype(int)
                                
                                ch_clean = re.sub(r'[^A-Z0-9*]', '', class_name.upper())
                                if ch_clean:
                                    cx = (bb[0] + bb[2]) / 2.0
                                    chars.append((cx, ch_clean))
                                    self.write_log(f"      YOLO Class: '{ch_clean}' @ x={cx:.1f}")

                        if chars:
                            sorted_chars =[c for _, c in sorted(chars, key=lambda x: x[0])]
                            raw_candidate = ''.join(sorted_chars)
                            self.write_log(f"    YOLO sorted: '{raw_candidate}'")
                            
                            normalized = self.normalize_size_candidate(raw_candidate)
                            if normalized:
                                weight = 5 if ('*' in raw_candidate and len(raw_candidate) >= 5) else 1
                                self.current_sizes.extend([normalized] * weight)
                                
                                found_data_this_frame = True
                                self.last_valid_data_frame = display_frame.copy()
                                self.last_valid_frame_number = frame_idx
                                self.write_log(f" → SIZE VOTED (YOLO): {normalized}")
                                continue  

                        self.write_log("    YOLO insufficient → PaddleOCR fallback")
                        try:
                            fallback_out = self.rec_model.predict(next_crop)
                            if fallback_out:
                                fallback_text = fallback_out[0]['rec_text'] if isinstance(fallback_out[0], dict) else fallback_out[0][0]
                                fallback_clean = re.sub(r'[^0-9*]', '', fallback_text)
                                normalized = self.normalize_size_candidate(fallback_clean)
                                if normalized:
                                    weight = 5 if ('*' in fallback_clean and len(fallback_clean) >= 5) else 1
                                    self.current_sizes.extend([normalized] * weight)
                                    
                                    found_data_this_frame = True
                                    self.last_valid_data_frame = display_frame.copy()
                                    self.last_valid_frame_number = frame_idx
                                    self.write_log(f" → SIZE VOTED (Paddle fallback): {normalized}")
                        except:
                            pass
                continue

            # ----------------------------------------------------
            # 2. DATE & SN DETECTION LOGIC (Using secondary YOLO)
            # ----------------------------------------------------
            if len(paddle_text_up) >= 8 and len(digits_only) >= 6:
                if re.search(r'(0202|202\d|10202|ST0|8T0|S10|S70|AST|O20|O70)', paddle_text_up):
                    self.write_log(f" → Date candidate triggered via Paddle context: '{paddle_text_up}'")
                    
                    date_crop = self.crop_polygon(frame, item['bounding_box'])
                    if date_crop is None or not getattr(self, "size_det_model", None): continue

                    # Predict bounding box string purely from size model character sorting
                    date_res = self.size_det_model(date_crop, verbose=False, device=settings.DEVICE_YOLO, conf=0.5, iou=0.45)
                    d_chars =[]
                    for dr in date_res:
                        for d_box in dr.boxes:
                            d_cls_id = int(d_box.cls[0])
                            d_name = self.size_det_model.names[d_cls_id]
                            d_ch = re.sub(r'[^A-Z0-9]', '', d_name.upper())
                            if d_ch:
                                dbb = d_box.xyxy[0].cpu().numpy()
                                d_chars.append(( (dbb[0]+dbb[2])/2.0, d_ch ))
                                
                    d_sorted = sorted(d_chars, key=lambda x: x[0])
                    yolo_date_raw = ''.join([c[1] for c in d_sorted])
                    self.write_log(f"    YOLO Date Raw String: '{yolo_date_raw}'")
                    
                    final_date = None
                    m_date = re.search(r'(20\d{6})', yolo_date_raw)
                    if m_date:
                        final_date = m_date.group(1)
                    else:
                        if len(yolo_date_raw) >= 11:
                            ignored_prefix_date = yolo_date_raw[3:]
                            m_sliced = re.search(r'^(\d{8})', ignored_prefix_date)
                            if m_sliced:
                                final_date = m_sliced.group(1)

                    if final_date:
                        self.current_dates.append(final_date)
                        self.found_date_for_current_profile = True
                        found_data_this_frame = True
                        self.last_valid_data_frame = display_frame.copy()
                        self.last_valid_frame_number = frame_idx
                        self.write_log(f"      → YOLO Final Date Applied: {final_date}")
                        
                        # Process SN (Next Box)
                        if idx + 1 < len(final_results):
                            sn_item = final_results[idx + 1]
                            sn_text_up = sn_item['text'].upper()
                            
                            if not self.is_group_like(sn_text_up):
                                sn_crop = self.crop_polygon(frame, sn_item['bounding_box'])
                                if sn_crop is not None:
                                    sn_res = self.size_det_model(sn_crop, verbose=False, device=settings.DEVICE_YOLO, conf=0.5, iou=0.45)
                                    s_chars =[]
                                    for sr in sn_res:
                                        for s_box in sr.boxes:
                                            s_cls = int(s_box.cls[0])
                                            s_cname = self.size_det_model.names[s_cls]
                                            s_ch = re.sub(r'[^A-Z0-9]', '', s_cname.upper())
                                            if s_ch:
                                                sbb = s_box.xyxy[0].cpu().numpy()
                                                s_chars.append(( (sbb[0]+sbb[2])/2.0, s_ch ))
                                    
                                    s_sorted = sorted(s_chars, key=lambda x: x[0])
                                    yolo_sn_raw = ''.join([c[1] for c in s_sorted])
                                    self.write_log(f"    YOLO SN Raw String (next box): '{yolo_sn_raw}'")
                                    
                                    sn_digits = re.sub(r'\D', '', yolo_sn_raw)
                                    if len(sn_digits) == 4:
                                        self.current_sns.append(sn_digits)
                                        found_data_this_frame = True
                                        self.last_valid_data_frame = display_frame.copy()
                                        self.last_valid_frame_number = frame_idx
                                        self.write_log(f"      → YOLO Final SN Applied: {sn_digits}")
                                    else:
                                        m_sn_bound = re.search(r'\b(\d{4})\b', yolo_sn_raw)
                                        m_sn_cons = re.search(r'(\d{4})', yolo_sn_raw)
                                        best_sn = m_sn_bound.group(1) if m_sn_bound else (m_sn_cons.group(1) if m_sn_cons else None)
                                        if best_sn:
                                            self.current_sns.append(best_sn)
                                            found_data_this_frame = True
                                            self.last_valid_data_frame = display_frame.copy()
                                            self.last_valid_frame_number = frame_idx
                                            self.write_log(f"      → YOLO Final SN Applied: {best_sn}")

        # --- SMART SILENCE LOGIC ---
        if not found_data_this_frame:
            self.silence_frame_counter += 1
            
            has_identity = bool(self.current_dates)
            has_sn = bool(self.current_sns)
            has_size = bool(self.current_sizes)
            
            # NEW RULE: NEVER reset threshold purely until we have collected BOTH Date + SN + Size.
            if has_identity and has_sn and has_size:
                current_threshold = settings.SILENCE_THRESHOLD_FRAMES
            else:
                current_threshold = settings.SILENCE_THRESHOLD_EXTENDED

            if self.silence_frame_counter > current_threshold:
                if self.current_dates or self.current_sns or self.current_sizes:
                    self.finalize_profile(f"Silence Trigger (Limit: {current_threshold})")
                self.silence_frame_counter = 0
        else:
            self.silence_frame_counter = 0

        if self.header_trigger_cooldown > 0: 
            self.header_trigger_cooldown -= 1
       
        if self.active_annotation_text:
            self._draw_text_with_background(display_frame, self.active_annotation_text, pos=(30, 60))
       
        t_end = time.time()
        dur_sec = t_end - t_start
        self.total_frame_processing_time += dur_sec
        self.processed_frame_count += 1
       
        msg = (f"Frame {frame_name_str} | Proc Time: {dur_sec*1000:.0f}ms | "
               f"Redis Latency: {latency_ms:.0f}ms | Txt: {full_text} | Device: {settings.DEVICE_YOLO}")
        self.write_log(msg)