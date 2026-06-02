import { Anomaly, Funnel, Heatmap } from "./api";
import { FeedItem, useCountUp } from "./hooks";

export function Card({ children, className = "", delay = 0 }:
  { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <div className={`card p-6 animate-fade-up hover:shadow-glow transition-shadow duration-500
      ${className}`} style={{ animationDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

export function Kpi({ label, value, suffix = "", sub, accent }:
  { label: string; value: number; suffix?: string; sub?: string; accent?: string }) {
  const v = useCountUp(value);
  const isPct = suffix === "%";
  return (
    <Card>
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">{label}</div>
      <div className="mt-2 flex items-end gap-1">
        <span className={`text-5xl font-semibold tnum tracking-tight ${accent ? "" : "text-ink"}`}
          style={accent ? { color: accent } : undefined}>
          {isPct ? v.toFixed(1) : Math.round(v)}
        </span>
        <span className="text-2xl font-medium text-ink-soft mb-1">{suffix}</span>
      </div>
      {sub && <div className="mt-1 text-[13px] text-ink-soft">{sub}</div>}
    </Card>
  );
}

export function Gauge({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value));
  const display = useCountUp(pct * 100);
  const R = 80, C = 2 * Math.PI * R, off = C * (1 - pct);
  return (
    <Card className="flex flex-col items-center justify-center">
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase self-start">Conversion Rate</div>
      <div className="relative my-2" style={{ width: 200, height: 200 }}>
        <svg width="200" height="200" className="-rotate-90">
          <circle cx="100" cy="100" r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="16" />
          <circle cx="100" cy="100" r={R} fill="none" stroke="url(#g)" strokeWidth="16"
            strokeLinecap="round" strokeDasharray={C} strokeDashoffset={off}
            style={{ transition: "stroke-dashoffset 1s cubic-bezier(.2,.7,.2,1)" }} />
          <defs>
            <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#34c759" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-semibold tnum">{display.toFixed(1)}%</span>
          <span className="text-[12px] text-ink-faint mt-1">of visitors bought</span>
        </div>
      </div>
    </Card>
  );
}

export function FunnelView({ funnel }: { funnel?: Funnel }) {
  const stages = funnel?.stages ?? [];
  const top = stages[0]?.count || 1;
  const labels: Record<string, string> = {
    entry: "Entered", zone_visit: "Browsed a zone", billing_queue: "Reached billing", purchase: "Purchased",
  };
  return (
    <Card delay={80}>
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">Conversion Funnel</div>
      <div className="mt-4 space-y-3">
        {stages.map((s, i) => (
          <div key={s.stage}>
            <div className="flex justify-between text-[13px] mb-1">
              <span className="font-medium text-ink">{labels[s.stage] ?? s.stage}</span>
              <span className="text-ink-soft tnum">{s.count} · {s.pct_of_entry}%</span>
            </div>
            <div className="h-9 rounded-xl bg-surface2/50 overflow-hidden">
              <div className="h-full rounded-xl flex items-center px-3 text-white text-[13px] font-medium
                transition-all duration-700 ease-out"
                style={{ width: `${Math.max(7, (100 * s.count) / top)}%`,
                  background: `linear-gradient(90deg,#3b82f6,${i === stages.length - 1 ? "#34c759" : "#5ac8fa"})` }}>
                {s.count > 0 ? s.count : ""}
              </div>
            </div>
            {i > 0 && s.drop_off_pct_from_prev > 0 &&
              <div className="text-[12px] text-red-400/80 mt-1">↓ {s.drop_off_pct_from_prev}% drop-off</div>}
          </div>
        ))}
      </div>
    </Card>
  );
}

export function HeatmapView({ heatmap }: { heatmap?: Heatmap }) {
  const zones = heatmap?.zones ?? [];
  const color = (s: number) => {
    // light-blue -> blue -> orange-red as intensity rises (Apple-ish heat ramp)
    const stops = [[233,240,247], [90,200,250], [0,113,227], [255,159,10], [255,59,48]];
    const t = Math.max(0, Math.min(1, s / 100)) * (stops.length - 1);
    const i = Math.floor(t), f = t - i, a = stops[i], b = stops[Math.min(i + 1, stops.length - 1)];
    const c = a.map((x, k) => Math.round(x + (b[k] - x) * f));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  };
  return (
    <Card delay={160}>
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">Zone Heatmap</div>
        {heatmap && <span className={`text-[11px] px-2 py-0.5 rounded-full ${heatmap.data_confidence === "low"
          ? "bg-yellow-500/15 text-yellow-400" : "bg-emerald-500/15 text-emerald-400"}`}>{heatmap.data_confidence} confidence</span>}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {zones.length === 0 && <div className="col-span-2 text-ink-faint text-sm py-6 text-center">No zone data yet</div>}
        {zones.map((z) => (
          <div key={z.zone_id} className="rounded-2xl p-4 text-white transition-all duration-700"
            style={{ background: color(z.freq_score) }}>
            <div className="font-semibold">{z.zone_id}</div>
            <div className="text-[12px] opacity-90 mt-1 tnum">{z.visits} visits · {z.avg_dwell_seconds}s dwell</div>
            <div className="mt-2 h-1.5 rounded-full bg-white/30 overflow-hidden">
              <div className="h-full bg-white/90 transition-all duration-700" style={{ width: `${z.freq_score}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

const sevStyle: Record<string, string> = {
  INFO: "border-brand/30/40 bg-brand/20/5", WARN: "border-warn/40 bg-warn/5", CRITICAL: "border-crit/40 bg-crit/5",
};
const sevDot: Record<string, string> = { INFO: "#3b82f6", WARN: "#ff9f0a", CRITICAL: "#ff3b30" };

export function AnomaliesView({ anomalies }: { anomalies?: Anomaly[] }) {
  const list = anomalies ?? [];
  return (
    <Card delay={120}>
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">Active Anomalies</div>
      <div className="mt-4 space-y-3">
        {list.length === 0 && (
          <div className="flex items-center gap-2 text-emerald-400 text-sm py-4">
            <span className="w-2 h-2 rounded-full bg-good" /> All systems nominal
          </div>
        )}
        {list.map((a, i) => (
          <div key={i} className={`rounded-2xl border p-4 ${sevStyle[a.severity] ?? ""}`}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: sevDot[a.severity] }} />
              <span className="font-semibold text-ink">{a.type.replace(/_/g, " ")}</span>
              <span className="ml-auto text-[11px] font-medium px-2 py-0.5 rounded-full bg-white/[0.08] text-ink-soft">
                {a.severity}</span>
            </div>
            <div className="text-[13px] text-ink-soft mt-2">{a.detail}</div>
            <div className="text-[13px] text-brand-2 mt-1">→ {a.suggested_action}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function Sparkline({ data }: { data: number[] }) {
  const w = 240, h = 56, pad = 4;
  const max = Math.max(1, ...data);
  const n = Math.max(1, data.length - 1);
  const pts = data.map((v, i) =>
    `${pad + (i * (w - 2 * pad)) / n},${h - pad - (v / max) * (h - 2 * pad)}`).join(" ");
  const last = data[data.length - 1] ?? 0;
  return (
    <Card delay={40}>
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">Event Throughput</div>
        <span className="text-[13px] text-ink-soft tnum">{last}/2s</span>
      </div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="mt-3" preserveAspectRatio="none">
        <defs>
          <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
        </defs>
        {data.length > 1 && (
          <>
            <polygon points={`${pad},${h - pad} ${pts} ${w - pad},${h - pad}`} fill="url(#spark)" />
            <polyline points={pts} fill="none" stroke="#3b82f6" strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />
          </>
        )}
      </svg>
    </Card>
  );
}

// Schematic store floor: zones placed like the real layout, intensity = heatmap freq.
const ZONE_POS: Record<string, { x: number; y: number; w: number; h: number }> = {
  STOCKROOM: { x: 4, y: 4, w: 28, h: 26 },
  SKINCARE: { x: 36, y: 4, w: 30, h: 42 },
  MAKEUP: { x: 70, y: 4, w: 26, h: 42 },
  BILLING: { x: 36, y: 50, w: 30, h: 30 },
  ENTRY: { x: 70, y: 50, w: 26, h: 30 },
};

export function ZoneMap({ heatmap }: { heatmap?: Heatmap }) {
  const byZone = new Map((heatmap?.zones ?? []).map((z) => [z.zone_id, z]));
  const heat = (s: number) => `rgba(0,113,227,${0.12 + 0.0085 * Math.min(100, s)})`;
  return (
    <Card delay={60}>
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">Store Floor Activity</div>
      <div className="relative mt-3 w-full" style={{ paddingBottom: "62%" }}>
        <div className="absolute inset-0 rounded-2xl bg-surface2/50 overflow-hidden">
          {Object.entries(ZONE_POS).map(([zid, p]) => {
            const z = byZone.get(zid);
            const score = z?.freq_score ?? 0;
            return (
              <div key={zid} className="absolute rounded-lg border border-line flex flex-col
                items-center justify-center text-center transition-all duration-700"
                style={{ left: `${p.x}%`, top: `${p.y}%`, width: `${p.w}%`, height: `${p.h}%`,
                  background: zid === "ENTRY" ? "rgba(52,199,89,0.18)" : heat(score) }}>
                <span className="text-[12px] font-semibold text-ink">{zid}</span>
                {z && <span className="text-[11px] text-ink-soft tnum">{z.visits} · {z.avg_dwell_seconds}s</span>}
                {zid === "ENTRY" && <span className="text-[11px] text-emerald-400">▲ entry</span>}
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}

export function EventFeed({ items, total, connected }:
  { items: FeedItem[]; total: number; connected: boolean }) {
  return (
    <Card delay={200} className="h-full">
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">Live Event Feed</div>
        <div className="flex items-center gap-2 text-[12px] text-ink-soft">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-good animate-pulse" : "bg-ink-faint"}`} />
          {total} events
        </div>
      </div>
      <div className="mt-3 space-y-1.5 max-h-[300px] overflow-auto pr-1">
        {items.length === 0 && <div className="text-ink-faint text-sm py-4">waiting for events…</div>}
        {items.map((it) => (
          <div key={it.id} className="flex items-center justify-between text-[13px] py-1.5 px-3 rounded-xl
            bg-surface2/50 animate-pop">
            <span className="font-medium text-ink">+{it.n} {it.type || "events"}</span>
            <span className="text-ink-faint tnum">{new Date(it.at).toLocaleTimeString()}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
