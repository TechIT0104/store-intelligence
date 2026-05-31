import { useDashboard, useEventStream, useTheme, useThroughput } from "./hooks";
import { AnomaliesView, EventFeed, FunnelView, Gauge, HeatmapView, Kpi,
         Sparkline, ZoneMap } from "./components";
import { UploadPanel } from "./UploadPanel";

export default function App() {
  const snap = useDashboard();
  const feed = useEventStream();
  const [dark, toggleTheme] = useTheme();
  const throughput = useThroughput(feed.total);
  const m = snap.metrics;
  const store = snap.health?.stores?.[0];

  return (
    <div className="min-h-screen">
      {/* top bar */}
      <header className="sticky top-0 z-10 glass border-b border-black/5">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent to-good" />
            <div>
              <div className="text-[15px] font-semibold tracking-tight leading-none">Store Intelligence</div>
              <div className="text-[12px] text-ink-faint mt-0.5">Apex Retail · {snap.metrics?.store_id ?? "—"}</div>
            </div>
          </div>
          <div className="flex items-center gap-4 text-[13px]">
            <span className={`flex items-center gap-1.5 ${snap.ok ? "text-good" : "text-warn"}`}>
              <span className={`w-2 h-2 rounded-full ${snap.ok ? "bg-good animate-pulse" : "bg-warn"}`} />
              {snap.ok ? "Live" : "Reconnecting"}
            </span>
            {store && (
              <span className={`px-2.5 py-1 rounded-full text-[12px] font-medium ${
                store.feed === "STALE_FEED" ? "bg-crit/10 text-crit" : "bg-good/10 text-good"}`}>
                {store.feed === "STALE_FEED" ? "Feed stale" : "Feed healthy"}
              </span>
            )}
            <button onClick={toggleTheme} aria-label="Toggle theme"
              className="w-9 h-9 rounded-full bg-black/5 dark:bg-white/10 flex items-center
                justify-center hover:bg-black/10 dark:hover:bg-white/20 transition-colors">
              {dark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-[28px] font-semibold tracking-tight">Today at a glance</h1>
          <p className="text-ink-soft text-[15px] mt-1">
            Real-time offline conversion intelligence · window anchored to the latest event
          </p>
        </div>

        {/* KPI row */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Kpi label="Unique Visitors" value={m?.unique_visitors ?? 0}
            sub={`${m?.converted_visitors ?? 0} converted · staff excluded`} />
          <Kpi label="Queue Depth" value={m?.queue_depth_max ?? 0}
            sub={`now ${m?.queue_depth_current ?? 0} · max today`} accent="#0071e3" />
          <Kpi label="Abandonment" value={(m?.abandonment_rate ?? 0) * 100} suffix="%"
            sub="left billing without buying" accent="#ff9f0a" />
          <Kpi label="Data Confidence" value={m?.unique_visitors ?? 0}
            sub={m?.data_confidence === "low" ? "low · < 20 sessions" : "high"} />
        </section>

        {/* gauge + funnel */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
          <Gauge value={m?.conversion_rate ?? 0} />
          <div className="lg:col-span-2"><FunnelView funnel={snap.funnel} /></div>
        </section>

        {/* deployed model: upload a video -> live detection output */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
          <div className="lg:col-span-2"><UploadPanel /></div>
          <ZoneMap heatmap={snap.heatmap} />
        </section>

        {/* heatmap + anomalies */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
          <HeatmapView heatmap={snap.heatmap} />
          <AnomaliesView anomalies={snap.anomalies?.anomalies} />
        </section>

        {/* live throughput + event feed */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
          <Sparkline data={throughput} />
          <div className="lg:col-span-2">
            <EventFeed items={feed.items} total={feed.total} connected={feed.connected} />
          </div>
        </section>

        <footer className="mt-10 text-center text-[12px] text-ink-faint">
          Detection (YOLOv8 + ByteTrack + Re-ID + VLM) → Redis → FastAPI → this dashboard, live.
        </footer>
      </main>
    </div>
  );
}
