# Detection microservice — YOLOv8 + ByteTrack served in-container (CPU).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_CONFIG_DIR=/app/.ultralytics

WORKDIR /app

# OpenCV + torch runtime libs (ultralytics pulls opencv-python which needs these).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch first (much smaller than the default CUDA build).
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY detection_service/requirements-service.txt .
RUN pip install -r requirements-service.txt

# Pre-download the YOLOv8n weights so the service starts fast and works offline.
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" && \
    ls -la yolov8n.pt

COPY pipeline ./pipeline
COPY detection_service ./detection_service
COPY data ./data

RUN useradd -m -u 10002 svc && chown -R svc /app
USER svc

EXPOSE 9000
HEALTHCHECK --interval=20s --timeout=4s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9000/health').status==200 else 1)" || exit 1
CMD ["uvicorn", "detection_service.server:app", "--host", "0.0.0.0", "--port", "9000"]
