# Simple Deployment Guide

## Option 1 — Local (fastest, zero cost, works NOW)
```bash
git clone https://github.com/TechIT0104/store-intelligence
cd store-intelligence
cp .env.example .env
docker compose up --build        # core stack — acceptance gate
# open http://localhost:8050
```
Full stack with deployed model:
```bash
docker compose --profile full up --build
```

## Option 2 — Railway (free, public URL, easy)

1. Go to https://railway.app → Sign in with GitHub
2. "New Project" → "Deploy from GitHub repo" → pick TechIT0104/store-intelligence
3. Railway auto-detects docker-compose. Add env vars manually:
   - DATABASE_URL  (Railway gives a free Postgres — copy the URL)
   - REDIS_URL     (Railway gives a free Redis — copy the URL)
   - SEED_EVENTS_PATH = /app/data/sample_events.jsonl
   - POS_CSV_PATH = /app/data/pos_transactions.csv
   - STORE_LAYOUT_PATH = /app/data/store_layout.json
4. For the static frontend: Vercel (free) or Netlify
   - Connect GitHub → pick store-intelligence → Root: frontend
   - Build: npm run build  → Publish: dist
   - Env: VITE_API_URL = your-railway-api-url

## Option 3 — Vercel (frontend only, instant)
The frontend is a static React app. Vercel deploys it for free in 2 minutes:
1. vercel.com → Import → TechIT0104/store-intelligence
2. Root directory: frontend
3. Build command: npm run build
4. Output: dist
5. Env: VITE_API_URL = http://localhost:8000 (or your Railway URL)

## Option 4 — Video demo as the "Demo Link"
The challenge is evaluated via `docker compose up`.
The safest Demo Link is a screen-recording video (upload to YouTube/Drive) showing:
- docker compose up → all containers healthy
- http://localhost:8050 → empty → Watch a Demo → live analytics
- Store Ops → real employee data
