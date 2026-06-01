import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { api, DetectJob, detect, TimeSeries } from "../api";
import { useDashboard, useEventStream, useThroughput } from "../hooks";
import {
  AnomaliesView, EventFeed, FunnelView, Gauge, HeatmapView, Kpi, Sparkline, ZoneMap,
} from "../components";
import { FootfallChart, ZoneBarChart } from "../charts";
import { UploadPanel } from "../UploadPanel";
import { Card } from "../components";
import { Loader } from "../Loading";

export function Dashboard() {
  const snap = useDashboard();
  const feed = useEventStream();
  const throughput = useThroughput(feed.total);
  const [ts, setTs] = useState<TimeSeries>();
  const m = snap.metrics;
  const hasData = (m?.unique_visitors ?? 0) > 0;

  useEffect(() => {
    const f = () => api.timeseries().then(setTs).catch(() => {});
    f(); const id = setInterval(f, 4000); return () => clearInterval(id);
  }, []);

  async function reset() { await api.reset(); setTs(undefined); }

  return (
    <>
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display font-bold text-3xl tracking-tight">Today at a glance</h1>
          <p className="text-ink-soft mt-1">
            Real-time offline conversion intelligence · Brigade Road (ST1008)
          </p>
        </div>
        <div className="flex items-center gap-3 text-[13px]">
          <span className={`flex items-center gap-1.5 ${snap.ok ? "text-good" : "text-warn"}`}>
            <span className={`w-2 h-2 rounded-full ${snap.ok ? "bg-good animate-pulse" : "bg-warn"}`} />
            {snap.ok ? "Live" : "Connecting"}
          </span>
          {hasData && (
            <button onClick={reset}
              className="chip text-ink-soft hover:text-crit hover:border-crit/40 transition-colors">
              ↺ Reset
            </button>
          )}
        </div>
      </div>

      {!hasData ? <EmptyState /> : <Analytics snap={snap} feed={feed} throughput={throughput} m={m} ts={ts} />}
    </>
  );
}

function Analytics({ snap, feed, throughput, m, ts }: any) {
  return (
    <>
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Unique Visitors" value={m?.unique_visitors ?? 0}
          sub={`${m?.converted_visitors ?? 0} converted · staff excluded`} />
        <Kpi label="Conversion" value={(m?.conversion_rate ?? 0) * 100} suffix="%"
          sub="visitors who purchased" accent="#a855f7" />
        <Kpi label="Queue Depth" value={m?.queue_depth_max ?? 0}
          sub={`now ${m?.queue_depth_current ?? 0} · max today`} accent="#22d3ee" />
        <Kpi label="Abandonment" value={(m?.abandonment_rate ?? 0) * 100} suffix="%"
          sub="left billing without buying" accent="#fbbf24" />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <Gauge value={m?.conversion_rate ?? 0} />
        <div className="lg:col-span-2"><FunnelView funnel={snap.funnel} /></div>
      </section>

      {/* live charts driven by the ingested events */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <FootfallChart data={ts} />
        <ZoneBarChart data={ts} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <div className="lg:col-span-2"><UploadPanel /></div>
        <ZoneMap heatmap={snap.heatmap} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <HeatmapView heatmap={snap.heatmap} />
        <AnomaliesView anomalies={snap.anomalies?.anomalies} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <Sparkline data={throughput} />
        <div className="lg:col-span-2">
          <EventFeed items={feed.items} total={feed.total} connected={feed.connected} />
        </div>
      </section>

      <footer className="mt-10 text-center text-[12px] text-ink-faint">
        Detection (YOLOv8 + ByteTrack + Re-ID + VLM) → Redis → FastAPI → this dashboard, live.
      </footer>
    </>
  );
}

function EmptyState() {
  const [demos, setDemos] = useState<{ clip: string; camera_id: string }[]>([]);
  const [job, setJob] = useState<DetectJob | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [running, setRunning] = useState(false);
  const poll = useRef<number | null>(null);

  useEffect(() => {
    detect.demos().then((d) => setDemos(d.demos ?? []));
    return () => { if (poll.current) clearInterval(poll.current); };
  }, []);

  async function fullDay() {
    setSeeding(true);
    await api.seedDemo();
    // the dashboard's 2.5s poll will pick up the data and switch views
  }

  async function runClip(clip: string) {
    setRunning(true); setJob(null);
    try {
      const j = await detect.runDemo(clip);
      setJob(j);
      poll.current = window.setInterval(async () => {
        const s = await detect.job(j.job_id);
        setJob(s);
        if (s.state === "done" || s.state === "error") {
          if (poll.current) clearInterval(poll.current);
          setRunning(false);
        }
      }, 1500);
    } catch (e: any) {
      setJob({ job_id: "", state: "error", error: String(e?.message ?? e) });
      setRunning(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}>
      <Card className="relative overflow-hidden text-center !p-10">
        <div className="absolute inset-0 grid-bg pointer-events-none" />
        <div className="relative">
          <div className="text-5xl mb-3">🎬</div>
          <h2 className="font-display font-bold text-2xl">Your store is quiet</h2>
          <p className="text-ink-soft mt-2 max-w-xl mx-auto">
            The dashboard is empty because it's waiting for a clip. Run a demo on a real
            CCTV clip, replay the full POS-grounded store day, or upload your own video —
            the deployed model produces the events you'll see here.
          </p>

          {seeding && <Loader label="Replaying the full store day…" />}
          {running && (
            <div className="mt-6 max-w-md mx-auto">
              <Loader label={job?.state === "detecting"
                ? `Running YOLOv8… ${job?.frames ?? 0} frames` : "Streaming events…"} />
              <div className="text-[12px] text-ink-faint">{job?.events_posted ?? 0} events emitted</div>
            </div>
          )}
          {job?.state === "error" && <div className="text-crit text-sm mt-4">{job.error}</div>}

          {!seeding && !running && (
            <div className="mt-8 space-y-5">
              <div>
                <div className="text-[12px] uppercase tracking-wide text-ink-faint mb-2">Watch a demo</div>
                <div className="flex flex-wrap justify-center gap-2">
                  <button onClick={fullDay}
                    className="grad-btn text-white px-5 py-2.5 rounded-xl font-semibold hover:scale-[1.03] transition-transform">
                    ▶ Full store day (POS-grounded)
                  </button>
                </div>
              </div>

              {demos.length > 0 && (
                <div>
                  <div className="text-[12px] uppercase tracking-wide text-ink-faint mb-2">
                    …or run the model on a real clip
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {demos.map((d, i) => (
                      <button key={d.clip} onClick={() => runClip(d.clip)}
                        className="glass px-4 py-2.5 rounded-xl text-sm font-semibold hover:bg-white/10 transition-colors">
                        Clip {i + 1} · {d.camera_id.replace("CAM_", "").replace("_01", "")}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-4 max-w-2xl mx-auto"><UploadPanel /></div>
            </div>
          )}
        </div>
      </Card>
    </motion.div>
  );
}
