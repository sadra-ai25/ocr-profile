# FROM registry.docker.ir/paddlepaddle/paddle:3.0.0b2-gpu-cuda11.8-cudnn8.9-trt8.5
# FROM paddlepaddle/paddle:3.1.0-gpu-cuda11.8-cudnn8.9

# FROM paddlepaddle/paddle:3.0.0b0-gpu-cuda11.8-cudnn8.9-trt8.5

FROM ocr:latest

ENV DEBIAN_FRONTEND=noninteractive

# RUN apt-get update && apt-get install -y \
#     libgl1 \
#     libglib2.0-0 \
#     libsm6 \
#     libxext6 \
#     libxrender-dev \
#     git \
#     curl \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# RUN python3 -m pip install --no-cache-dir --upgrade pip && \
#     python3 -m pip install --no-cache-dir \
#     paddleocr==3.1.0 \
#     paddlepaddle-gpu==3.0.0 \
#     paddlex==3.0.0 \
#     lanms-neo==1.0.2 \
#     Polygon3

# COPY requirements.txt .

# RUN python3 -m pip install --no-cache-dir \
#     torch==2.1.2+cu118 \
#     torchvision==0.16.2+cu118 \
#     torchaudio==2.1.2+cu118 \
#     --extra-index-url https://download.pytorch.org/whl/cu118

# RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY ./src /app/src
COPY .env /app/.env

ENV PYTHONPATH="/app/src:${PYTHONPATH}"
RUN ln -sf /usr/bin/python3 /usr/bin/python

# CMD ["uvicorn", "api.endpoint:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
CMD []


