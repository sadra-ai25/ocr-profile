# Profile OCR — Steel Profile Size Reader

![Python](https://img.shields.io/badge/Python-3.10-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-green) ![YOLOv8](https://img.shields.io/badge/YOLOv8-Detection-red) ![PaddleOCR](https://img.shields.io/badge/PaddleOCR-v5-orange) ![Redis](https://img.shields.io/badge/Redis-Queue-red) ![Docker](https://img.shields.io/badge/Docker-Compose-blue)

Automated OCR system for reading size markings stenciled on steel profiles on a production line. Uses YOLOv8 to detect the text region and PP-OCRv5 to read the size code, then logs each reading to a database.

## Features

- **Two-stage pipeline** — YOLOv8 localizes the label area; PaddleOCR reads the size text
- **Fuzzy text matching** — post-OCR normalization handles common OCR errors (e.g. `6ROUP` → `GROUP`, `0` vs `O`) using variant lists and regex cleanup
- **ROI cropping** — configurable ROI region narrows the search area for faster, more accurate OCR
- **GPU acceleration** — optional CUDA support via `USE_GPU` and `CUDA_VISIBLE_DEVICES`
- **Redis frame queue** — decoupled producer/consumer for reliable stream processing
- **RTSP stream support** — connects to any IP camera
- **Database logging** — each recognized size is persisted with timestamp and camera ID
- **REST API** — start/stop stream processing and query recent readings

## Tech Stack

| Component | Technology |
|---|---|
| Profile Detector | YOLOv8 (Ultralytics) |
| OCR Engine | PaddleOCR PP-OCRv5 Server |
| API Server | FastAPI + Uvicorn |
| Frame Queue | Redis |
| Containerization | Docker Compose |
| Camera Capture | OpenCV |

## Architecture

```
RTSP Camera
      │
      ▼
 Camera Producer (Thread)
   - Captures frames
   - Pushes to Redis queue
      │
      ▼
  Redis Queue
      │
      ▼
 AI Processor (Thread)
   ├── Step 1: Crop frame to ROI (ROI_X, ROI_Y, ROI_W, ROI_H)
   ├── Step 2: YOLOv8 detects label region within ROI
   ├── Step 3: Crop detected label → PaddleOCR reads size text
   └── Step 4: Log result (size, confidence, timestamp) to DB
      │
      ▼
 FastAPI REST API  (readings & status)
```

## Prerequisites

- Docker & Docker Compose
- YOLOv8 model weights at `src/ai/weights/best.pt`
- PaddleOCR PP-OCRv5 server model at `src/ai/weights/PP-OCRv5_server_rec/`
- (Optional) NVIDIA GPU with CUDA for accelerated inference

## Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/sadra-ai25/ocr-profile.git
cd ocr-profile

# 2. Configure environment
cp .env.example .env   # edit with your values

# 3. Place model weights
mkdir -p src/ai/weights
cp /path/to/best.pt src/ai/weights/
cp -r /path/to/PP-OCRv5_server_rec src/ai/weights/

# 4. Start services
docker compose up -d --build
```

## Configuration

| Key | Description | Example |
|---|---|---|
| `USE_GPU` | Enable GPU inference | `true` |
| `CUDA_VISIBLE_DEVICES` | GPU device index | `0` |
| `MODEL_PATH_YOLO` | YOLOv8 weights path | `/app/src/ai/weights/best.pt` |
| `MODEL_DIR_PADDLE` | PaddleOCR model directory | `/app/src/ai/weights/PP-OCRv5_server_rec` |
| `RTSP_URL` | Camera RTSP stream | `rtsp://mediamtx:8554/mystream` |
| `REDIS_HOST` | Redis hostname | `redis` |
| `REDIS_PORT` | Redis port | `6379` |
| `FRAME_INTERVAL` | Process every Nth frame | `1` |
| `ROI_X` | ROI start X pixel | `3` |
| `ROI_Y` | ROI start Y pixel | `328` |
| `ROI_W` | ROI width in pixels | `1846` |
| `ROI_H` | ROI height in pixels | `254` |

## API Endpoints

The RTSP pipeline starts automatically on service startup. Use these endpoints to control it:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service health — returns status and active device (CPU/GPU) |
| `POST` | `/rtsp/start` | (Re)start RTSP stream, optionally with a session name |
| `POST` | `/rtsp/stop` | Stop RTSP stream processing |
| `POST` | `/video` | Upload a video file for analysis (background task) |
| `POST` | `/reports` | Query profile OCR results with optional time range filter |

### Example: Start RTSP with Session Name

```bash
curl -X POST "http://localhost:8000/rtsp/start?session_name=morning_shift"
```

### Example: Query Readings for a Time Range

```bash
curl -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -d '{"start_time": "2024-01-15 07:00:00", "end_time": "2024-01-15 15:00:00"}'
```

```json
{
  "status": "success",
  "count": 58,
  "data": [
    {"profile_type": "IPE160", "timestamp": "2024-01-15T08:23:45"},
    {"profile_type": "GROUP",  "timestamp": "2024-01-15T09:11:02"}
  ]
}
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first.

## License

MIT
