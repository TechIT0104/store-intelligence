#!/usr/bin/env bash
# Run the detection pipeline against all CCTV clips -> pipeline/output/events.jsonl
# Runs on the HOST (uses the GPU). See README for the one-time venv setup.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root (store-intelligence/)

# Load .env if present (CLIPS_DIR, YOLO_MODEL, SAMPLE_FPS, DEVICE, GEMINI_API_KEY)
if [ -f .env ]; then set -a; . ./.env; set +a; fi

CLIPS_DIR="${CLIPS_DIR:-../CCTV Footage-20260529T160731Z-3-00144614ea/CCTV Footage}"
OUT="${EVENTS_OUT:-pipeline/output/events.jsonl}"

echo "Clips dir : $CLIPS_DIR"
echo "Output    : $OUT"
echo "Model     : ${YOLO_MODEL:-yolov8n.pt}  Sample fps: ${SAMPLE_FPS:-5}  Device: ${DEVICE:-0}"

python -m pipeline.detect \
  --clips-dir "$CLIPS_DIR" \
  --layout data/store_layout.json \
  --out "$OUT" \
  --model "${YOLO_MODEL:-yolov8n.pt}" \
  --sample-fps "${SAMPLE_FPS:-5}" \
  --device "${DEVICE:-0}"

echo "Done. Events at $OUT"
echo "Now bring up the API and replay:  docker compose up --build"
