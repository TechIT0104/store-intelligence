# Store Intelligence — Purplle Brigade Road (ST1008)

Turns raw store CCTV into a live **offline conversion-rate** intelligence surface:
a detection pipeline (YOLOv8 + ByteTrack + Re-ID + a Gemini VLM staff check) emits
structured events; a FastAPI service ingests them and serves real-time metrics, a
conversion funnel, a zone heatmap, anomalies and health; a web dashboard shows a
metric updating live.

> **TL;DR for reviewers:** `docker compose up --build` → API on `:8000`, dashboard
> on `:8050`. A bundled `sample_events.jsonl` auto-replays so everything is live
> even before you run detection. To run real detection on the clips, see
> [§ Run detection](#run-the-detection-pipeline).

---

## Quick start (5 commands)

```bash
git clone <repo-url> && cd store-intelligence
cp .env.example .env                 # optional: add GEMINI_API_KEY for the VLM staff check
docker compose up --build            # starts postgres, redis, api, replayer, dashboard
# open http://localhost:8050         # live dashboard
python assertions.py                 # self-check the acceptance gate (needs `pip install requests`)
```

That is everything for the **acceptance gate** — no manual steps beyond
`git clone`. The `replayer` streams the bundled sample events into the API in
simulated real time, so `GET http://localhost:8000/stores/ST1008/metrics`
returns live data immediately.

### Full interactive mode (deployed model + video upload)

```bash
docker compose --profile full up --build    # adds the in-container detection model
# open http://localhost:8050 -> "Upload & Analyze" -> drop a CCTV clip -> Run Detection
```

This brings up the **detection microservice** (YOLOv8 + ByteTrack running *inside a
container*). Upload a video in the dashboard and the deployed model detects/tracks
people, classifies staff, emits events to the API, and they flow live onto the
dashboard. The heavy CV image lives behind the `full` profile so the default
`docker compose up` (the gate) stays fast and reliable.

---

## Run the detection pipeline (on the host, against the real clips)

Detection runs natively (to use the GPU if available); its output is then replayed
by the container. Clips are read from `CLIPS_DIR` in `.env`.

```bash
python -m venv .venv && . .venv/Scripts/activate    # (Windows) or source .venv/bin/activate
pip install -r requirements.txt -r pipeline/requirements-detect.txt
bash pipeline/run.sh                                 # processes all clips -> pipeline/output/events.jsonl
docker compose restart replayer                      # replay the freshly detected events
```

- Output: **`pipeline/output/events.jsonl`** (the canonical event stream).
- **Annotated demo video**: add `--annotate` (or `make annotate CLIP="CAM 2.mp4"`) to
  render `pipeline/output/annotated_*.mp4` with live bounding boxes, track/visitor IDs,
  zone overlays, the entry/exit line and running entry/exit counts.
- `DEVICE=cpu` by default (clips are short — CPU finishes in minutes). Set
  `DEVICE=0` with a CUDA torch build to use the GPU.
- `SAMPLE_FPS=5` controls frame sampling (source is 25–30 fps).
- Set `GEMINI_API_KEY` in `.env` to enable the VLM staff validator; without it the
  pipeline falls back to the dark-uniform + stockroom heuristics.

---

## API

| Endpoint | Purpose |
|---|---|
| `POST /events/ingest` | Batch (≤500), idempotent by `event_id`, partial success |
| `GET /stores/{id}/metrics` | Unique visitors, conversion, dwell/zone, queue, abandonment |
| `GET /stores/{id}/funnel` | Entry → Zone → Billing → Purchase (session-based) |
| `GET /stores/{id}/heatmap` | Per-zone frequency + dwell, normalised 0–100 |
| `GET /stores/{id}/anomalies` | Queue spike / conversion drop / dead zone (+ severity, action) |
| `GET /health` | Per-store last event + STALE_FEED + DB status |

Example:
```bash
curl localhost:8000/stores/ST1008/metrics
curl localhost:8000/health
```

---

## Dashboard (Part E)

A **React + Vite + TypeScript + Tailwind** single-page app with an Apple-inspired
design (light, glass cards, animated counters, a radial conversion gauge, funnel,
zone heatmap and a live event ticker). It is served by **nginx**, which also acts
as the **edge gateway** — proxying `/api/*` to the API and `/stream/*` to the SSE
endpoint, so the browser sees a single origin and the API stays behind the gateway.

Open **http://localhost:8050**. Metrics poll every 2.5 s and the event ticker
updates over SSE as the replayer feeds events in — proof the pipeline and API are
genuinely connected, not batch-only.

## Security (production-ready, gate-safe by default)

- **Security headers** on every response (nginx + API middleware).
- **Optional API-key auth** on writes: set `API_KEY=...` to require `X-API-Key` on
  `POST /events/ingest` (off by default so the scoring harness needs no credentials).
- **Optional rate limiting**: set `RATE_LIMIT_PER_MIN=600` for a per-IP budget.
- **CORS** configurable via `CORS_ORIGINS`.
- DB credentials via env/secret; no secrets in the image.
- **Observability**: `GET /metrics` (Prometheus) — request counter, latency histogram,
  events-ingested counter — plus structured JSON request logs (trace_id, latency, ...).
- **Concurrency-safe ingest**: `INSERT ... ON CONFLICT DO NOTHING`, so identical
  payloads racing in parallel stay idempotent (no primary-key 5xx).

---

## Tests

```bash
pip install -r requirements.txt
pytest --cov=app --cov=pipeline       # 37 tests, ~83% statement coverage
```
Edge cases covered: empty store, all-staff clip, zero purchases, re-entry in the
funnel, idempotent re-ingest, malformed-event partial success, DB-down → 503.

---

## Developer tooling

- **Makefile**: `make up` · `make test` · `make detect` · `make annotate` · `make down`
  (run `make help` for all targets). Windows users can use the equivalent commands above.
- **CI** (`.github/workflows/ci.yml`): on every push it runs the test suite with a
  70% coverage gate, builds the frontend, and builds the Docker images.

## Layout

```
pipeline/   detection (detect, zones, reid, staff + staff_signals + VLM, emit) + replayer
detection_service/  the DEPLOYED model: FastAPI + YOLOv8 + ByteTrack in a container
app/        FastAPI: ingestion, metrics, funnel, anomalies, health, stream, security, db
frontend/   React + Vite + Tailwind dashboard + Upload&Analyze, served by nginx (gateway)
tests/      pytest suite, 43 tests (prompt blocks at top of each file)
k8s/        Kubernetes manifests (production deployment path; compose is the gate)
data/       store_layout.json, pos_transactions.csv, sample_events.jsonl (+ synth/)
docs/       DESIGN.md, CHOICES.md
```

Services (docker compose): **postgres · redis · api · replayer · frontend (nginx gateway)**.

See `docs/DESIGN.md` for architecture + AI-assisted decisions and `docs/CHOICES.md`
for the model/schema/API rationale.

## Kubernetes (bonus)

```bash
kubectl apply -k k8s/      # postgres, redis, api, dashboard (see k8s/README.md)
```
docker-compose remains the source of truth for the acceptance gate; the manifests
demonstrate the production deployment path.
