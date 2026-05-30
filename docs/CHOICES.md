# CHOICES.md — Key Decisions

Three decisions, each with the options considered, what the AI suggested, and
what we chose and why.

---

## Decision 1 — Detection model: **YOLOv8n + ByteTrack**

**Options considered**
- YOLOv8n / YOLOv8s / YOLOv9 / RT-DETR for detection
- ByteTrack vs DeepSORT vs StrongSORT for tracking
- A dedicated Re-ID network (OSNet/torchreid) vs a distance-based signature

**What the AI suggested.** When we described the hardware (GTX 1650, 4 GB VRAM)
and the clip length (~2.5 min each, 1080p), the LLM recommended YOLOv8n as the
sweet spot and ByteTrack because it is bundled with ultralytics (no extra
training or weights) and is robust to short occlusions. For Re-ID it floated both
OSNet and a lighter histogram approach.

**What we chose and why.** **YOLOv8n + ByteTrack + a histogram-based
VisitorRegistry.**
- YOLOv8n: person detection is not the hard part here; n-size keeps inference fast
  enough to run the whole dataset on CPU in minutes, and fits 4 GB if GPU is used.
  We kept the confidence threshold low (0.25) and **flag** low-confidence
  detections rather than dropping them, because the rubric scores confidence
  calibration and partial occlusion.
- ByteTrack: zero extra setup, good ID stability across brief occlusions.
- We **overrode** the OSNet suggestion. A full Re-ID net is overkill for a single
  store and adds a heavy dependency; an 8×8×8 HSV histogram + temporal gating is
  explainable, fast, and good enough to catch re-entry and cross-camera overlap.
  Its **known failure** (two people in similar dark clothing within a few seconds
  can merge) is documented and mitigated by requiring a prior EXIT before REENTRY.

**VLM usage + evaluation.** We use Gemini 2.5 Flash as a **staff-detection
validator** (not the primary path). Prompt (also in `DESIGN.md` / `pipeline/staff.py`):
> *"…Store STAFF wear a dark/black uniform top and stand behind counters;
> CUSTOMERS wear varied colours and browse… answer strictly as JSON
> {is_staff, confidence, reason}."*

On the billing frame it returned `staff_count: 3, customer_count: 0` with the
note that all three wore dark uniforms — **it worked**, and confirmed our
heuristic. We **overrode** calling it per-frame (latency/cost): it is invoked only
on ambiguous crops (heuristic 0.3–0.7), once per track, with the heuristic as the
default. If the heuristic ever proved unreliable in a new store, we would raise
the VLM's role from validator to primary — that is the trigger to change the
decision.

---

## Decision 2 — Event schema design

**Options considered**
- A flat schema vs a nested `metadata` object
- Rejecting malformed/low-confidence events at the edge vs carrying everything
- Where the session ordinal lives

**What the AI suggested.** A flat schema for query simplicity, and rejecting
events below a confidence threshold to "keep the data clean."

**What we chose and why.** We kept the **challenge's nested schema** (top-level
behavioural fields + a `metadata` object for `queue_depth`, `sku_zone`,
`session_seq`) for two reasons: (1) it matches the held-out scoring schema exactly,
and (2) `metadata` is forward-compatible — the Pydantic model uses `extra="allow"`
so a future field doesn't break ingestion. We **overrode** the "drop low
confidence" advice: suppressing low-confidence events would destroy recall on the
exact partial-occlusion cases the rubric tests, and hide calibration. Instead we
**carry confidence through** and let the API decide. `session_seq` lives in
`metadata` and is assigned by the emitter, giving every event a stable position in
its visitor's session — which is what makes session-based funnel de-duplication
trivial downstream.

---

## Decision 3 — API architecture: **modular monolith + Postgres, container-per-concern**

**Options considered**
- Storage: SQLite vs PostgreSQL
- True micro-services vs a modular monolith
- Caching/event-stream: none vs Redis vs Kafka

**What the AI suggested.** SQLite "is fine for a take-home", and warned that full
micro-services in a 1–2 day window is high-risk.

**What we chose and why.** **PostgreSQL + a modular-monolith API + Redis**, all as
separate containers in one compose file.
- **Postgres over SQLite**: we *agreed with the spirit* of the SQLite suggestion
  (simplicity) but chose Postgres because it makes the **graceful-degradation**
  requirement real — stopping the `postgres` container makes the API return a
  structured **503**, which we test. With SQLite that scenario is contrived.
  SQLite remains the default for zero-infra local dev and the test suite.
- **Modular monolith over micro-services**: we **agreed** with the AI's risk
  warning. The API is split into clear modules but deployed as one service, so
  debugging stays cheap. Separate *infrastructure* (DB, cache, replayer,
  dashboard) still gives a service-oriented topology.
- **Redis over Kafka**: Redis Streams/pub-sub is the "event stream" (Stage 2 into
  Stage 3) and powers the live dashboard. Kafka would be the right answer at 40
  live stores, but is operational overkill for this submission — a deliberate,
  documented trade-off rather than an oversight.
