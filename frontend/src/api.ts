// API client. All calls go through the relative `/api` prefix, which nginx
// proxies to the api service (and Vite proxies in dev).

const STORE = "ST1008";

// Local (docker): calls go through nginx — API at /api, SSE at /stream, detection
// at /detect. Cloud (Render static site): VITE_API_URL points at the api service.
// Render injects a bare host (no scheme), so prepend https:// when needed.
const _raw = (import.meta.env.VITE_API_URL || "").trim();
const _abs = _raw && !/^https?:\/\//.test(_raw) ? `https://${_raw}` : _raw;
const API_BASE = _abs || "/api";
const STREAM_BASE = _abs || "";

export type Metrics = {
  store_id: string;
  window: { start: string; end: string };
  unique_visitors: number;
  converted_visitors: number;
  conversion_rate: number;
  avg_dwell_seconds_per_zone: Record<string, number>;
  queue_depth_current: number;
  queue_depth_max: number;
  abandonment_rate: number;
  data_confidence: string;
};

export type FunnelStage = {
  stage: string;
  count: number;
  drop_off_pct_from_prev: number;
  pct_of_entry: number;
};
export type Funnel = { stages: FunnelStage[]; overall_conversion_rate: number };

export type HeatZone = {
  zone_id: string;
  visits: number;
  avg_dwell_seconds: number;
  freq_score: number;
  dwell_score: number;
};
export type Heatmap = { zones: HeatZone[]; sessions: number; data_confidence: string };

export type Anomaly = {
  type: string;
  severity: "INFO" | "WARN" | "CRITICAL";
  detail: string;
  suggested_action: string;
};
export type Anomalies = { anomalies: Anomaly[]; active_count: number; as_of: string };

export type Health = {
  status: string;
  db: string;
  stale_feed: boolean;
  stores: { store_id: string; events: number; feed: string; last_event_ts: string | null }[];
};

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { accept: "application/json" } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export type DetectJob = {
  job_id: string;
  state: "queued" | "detecting" | "streaming" | "done" | "error";
  filename?: string;
  frames?: number;
  events_total?: number;
  events_posted?: number;
  entry?: number;
  exit?: number;
  visitors?: number;
  staff?: number;
  zones?: Record<string, number>;
  error?: string;
};

export const detect = {
  available: async (): Promise<boolean> => {
    try {
      const r = await fetch("/detect/health");
      return r.ok;
    } catch {
      return false;
    }
  },
  cameras: async () => {
    const r = await fetch("/detect/cameras");
    return r.ok ? r.json() : { cameras: [] };
  },
  upload: async (file: File, camera_id: string, fps = 5): Promise<DetectJob> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("store_id", STORE);
    fd.append("camera_id", camera_id);
    fd.append("sample_fps", String(fps));
    const r = await fetch("/detect/jobs", { method: "POST", body: fd });
    if (!r.ok) throw new Error(`upload failed (${r.status})`);
    return r.json();
  },
  job: async (id: string): Promise<DetectJob> => {
    const r = await fetch(`/detect/jobs/${id}`);
    return r.json();
  },
  demos: async (): Promise<{ demos: { clip: string; camera_id: string }[]; available: boolean }> => {
    try {
      const r = await fetch("/detect/demos");
      return r.ok ? r.json() : { demos: [], available: false };
    } catch {
      return { demos: [], available: false };
    }
  },
  runDemo: async (clip: string): Promise<DetectJob> => {
    const fd = new FormData();
    fd.append("clip", clip);
    fd.append("store_id", STORE);
    const r = await fetch("/detect/demos/run", { method: "POST", body: fd });
    if (!r.ok) throw new Error(`demo failed (${r.status})`);
    return r.json();
  },
};

export type StaffMember = {
  salesperson: string; employee_code: string; transactions: number;
  customers_attended: number; items_sold: number; revenue_inr: number;
  avg_basket_inr: number; shift_hours: number; longest_break_min: number;
  took_lunch_break: boolean; utilisation: number;
};
export type TimeSeries = {
  series: { hour: string; entries: number; sales: number }[];
  zones: { zone: string; visits: number }[];
};

export type StaffOps = {
  staff_count: number;
  summary: { total_revenue_inr: number; total_transactions: number; total_items: number;
             top_performer: string | null; avg_utilisation: number };
  staff: StaffMember[];
};

export const api = {
  store: STORE,
  metrics: () => get<Metrics>(`/stores/${STORE}/metrics`),
  funnel: () => get<Funnel>(`/stores/${STORE}/funnel`),
  heatmap: () => get<Heatmap>(`/stores/${STORE}/heatmap`),
  anomalies: () => get<Anomalies>(`/stores/${STORE}/anomalies`),
  staff: () => get<StaffOps>(`/stores/${STORE}/staff`),
  timeseries: () => get<TimeSeries>(`/stores/${STORE}/timeseries`),
  health: () => get<Health>(`/health`),
  seedDemo: async () => {
    const r = await fetch(`${API_BASE}/demo/seed`, { method: "POST" });
    return r.ok ? r.json() : { seeded: 0 };
  },
  reset: async () => {
    const r = await fetch(`${API_BASE}/demo/reset`, { method: "POST" });
    return r.ok ? r.json() : { deleted: 0 };
  },
  streamUrl: () => `${STREAM_BASE}/stream/${STORE}`,
};
