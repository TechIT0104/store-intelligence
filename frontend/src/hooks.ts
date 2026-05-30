import { useEffect, useRef, useState } from "react";
import { api, Anomalies, Funnel, Health, Heatmap, Metrics } from "./api";

export type Snapshot = {
  metrics?: Metrics;
  funnel?: Funnel;
  heatmap?: Heatmap;
  anomalies?: Anomalies;
  health?: Health;
  ok: boolean;
  lastUpdated?: number;
};

export function useDashboard(pollMs = 2500): Snapshot {
  const [snap, setSnap] = useState<Snapshot>({ ok: false });
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const [metrics, funnel, heatmap, anomalies, health] = await Promise.all([
          api.metrics(), api.funnel(), api.heatmap(), api.anomalies(), api.health(),
        ]);
        if (alive) setSnap({ metrics, funnel, heatmap, anomalies, health, ok: true, lastUpdated: Date.now() });
      } catch {
        if (alive) setSnap((s) => ({ ...s, ok: false }));
      }
    };
    tick();
    const id = setInterval(tick, pollMs);
    return () => { alive = false; clearInterval(id); };
  }, [pollMs]);
  return snap;
}

export type FeedItem = { id: number; n: number; type: string; at: number };

export function useEventStream() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [total, setTotal] = useState(0);
  const [connected, setConnected] = useState(false);
  const idRef = useRef(0);
  useEffect(() => {
    const es = new EventSource(api.streamUrl());
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      let n = 1, type = "";
      try { const o = JSON.parse(e.data); n = o.n ?? 1; type = o.last?.event_type ?? ""; } catch { return; }
      setTotal((t) => t + n);
      setItems((prev) => [{ id: idRef.current++, n, type, at: Date.now() }, ...prev].slice(0, 40));
    };
    return () => es.close();
  }, []);
  return { items, total, connected };
}

export function useCountUp(value: number, ms = 600): number {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  useEffect(() => {
    const from = fromRef.current;
    const start = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / ms);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(from + (value - from) * eased);
      if (p < 1) raf = requestAnimationFrame(step);
      else fromRef.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return display;
}
