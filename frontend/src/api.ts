// API client. All calls go through the relative `/api` prefix, which nginx
// proxies to the api service (and Vite proxies in dev).

const STORE = "STORE_BLR_002";

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
  const r = await fetch(`/api${path}`, { headers: { accept: "application/json" } });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const api = {
  store: STORE,
  metrics: () => get<Metrics>(`/stores/${STORE}/metrics`),
  funnel: () => get<Funnel>(`/stores/${STORE}/funnel`),
  heatmap: () => get<Heatmap>(`/stores/${STORE}/heatmap`),
  anomalies: () => get<Anomalies>(`/stores/${STORE}/anomalies`),
  health: () => get<Health>(`/health`),
  streamUrl: () => `/stream/${STORE}`,
};
