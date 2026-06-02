import { motion } from "framer-motion";
import { Link } from "react-router-dom";

const rise = (d: number) => ({
  initial: { opacity: 0, y: 20 }, animate: { opacity: 1, y: 0 },
  transition: { duration: 0.55, delay: d, ease: [0.2, 0.7, 0.2, 1] as const },
});

const FEATURES = [
  { icon: "🎥", title: "Live Detection",     desc: "YOLOv8 + ByteTrack running in a container — upload a clip or run on pre-mounted CCTV footage." },
  { icon: "📊", title: "Real-time API",      desc: "FastAPI + Postgres + Redis. Conversion funnel, zone heatmaps, anomalies — correlated with real POS." },
  { icon: "🧠", title: "Staff AI",           desc: "Multi-signal staff classifier: access zones, behaviour, Gemini VLM action recognition." },
  { icon: "🏪", title: "Store Operations",   desc: "Employee tracking from real POS: shift hours, lunch breaks, utilisation, top performer." },
];

const HOW = [
  { n: "01", t: "Open the Dashboard", d: "It starts empty — waiting for a clip, like a fresh store feed." },
  { n: "02", t: "Run a Demo",          d: "Replay the full POS-grounded store day, or run the deployed model on a real CCTV clip." },
  { n: "03", t: "Upload Your Own",     d: "Drop any video. The containerised model detects, tracks and emits live events." },
  { n: "04", t: "Explore Insights",   d: "Conversion, funnel, heatmaps, charts, anomalies, and the Store Ops employee dashboard." },
];

export function Landing() {
  return (
    <div className="min-h-screen" style={{ background: "#060d1a" }}>
      {/* nav */}
      <header className="border-b border-line" style={{ background: "#080f1e" }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg grad-btn flex items-center justify-center">
              <span className="text-white text-[13px] font-bold">SI</span>
            </div>
            <span className="font-display font-bold text-[15px]">Store Intelligence</span>
          </div>
          <nav className="flex items-center gap-4 text-[13px]">
            <a href="#about" className="text-ink-soft hover:text-ink transition-colors">About</a>
            <a href="#how"   className="text-ink-soft hover:text-ink transition-colors">How it works</a>
            <Link to="/dashboard"
              className="grad-btn text-white px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity">
              Open App
            </Link>
          </nav>
        </div>
      </header>

      {/* hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 grid-bg pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-64
          bg-blue-500/8 blur-3xl rounded-full pointer-events-none" />

        <div className="relative max-w-7xl mx-auto px-6 py-24 grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <motion.div {...rise(0)}
              className="inline-flex items-center gap-2 mb-5 px-3 py-1.5 rounded-full
                border border-line text-[12px] text-ink-soft">
              <span className="w-1.5 h-1.5 rounded-full animate-pulseglow" style={{ background: "#10b981" }} />
              Purplle · Brigade Road · ST1008
            </motion.div>

            <motion.p {...rise(0.03)} className="text-[13px] text-ink-soft uppercase tracking-widest mb-3">
              Welcome to
            </motion.p>
            <motion.h1 {...rise(0.07)}
              className="font-display font-extrabold text-5xl sm:text-6xl leading-[1.06]">
              <span className="grad-text">Store</span><br />
              <span className="text-ink">Intelligence</span>
            </motion.h1>
            <motion.p {...rise(0.15)} className="mt-5 text-[16px] text-ink-soft leading-relaxed max-w-lg">
              Turn raw CCTV footage into the offline <b className="text-ink">conversion rate</b>,
              a customer funnel, zone heatmaps and employee ops — correlated with real POS sales.
            </motion.p>

            <motion.div {...rise(0.22)} className="mt-8 flex flex-wrap gap-3">
              <Link to="/dashboard"
                className="grad-btn text-white px-6 py-3 rounded-xl font-semibold
                  hover:scale-[1.02] transition-transform">
                Launch Dashboard →
              </Link>
              <Link to="/operations"
                className="px-6 py-3 rounded-xl font-semibold border border-line
                  text-ink-soft hover:text-ink hover:border-line2 transition-colors">
                Store Operations
              </Link>
            </motion.div>

            <motion.div {...rise(0.30)} className="mt-10 flex gap-8">
              {[["31.6%","conversion"],["24","purchases (POS)"],["5","cameras"],["6","staff tracked"]].map(([v, l]) => (
                <div key={l}>
                  <div className="font-display font-bold text-[22px] grad-text">{v}</div>
                  <div className="text-[11px] text-ink-faint mt-0.5">{l}</div>
                </div>
              ))}
            </motion.div>
          </div>

          {/* live preview card */}
          <motion.div {...rise(0.18)} className="relative">
            <div className="card p-6 animate-float">
              <div className="flex items-center justify-between mb-4">
                <span className="text-[11px] uppercase tracking-wider text-ink-faint">Live · Today</span>
                <span className="badge badge-green">● Healthy feed</span>
              </div>
              <div className="flex items-baseline gap-2 mb-5">
                <span className="font-display font-extrabold text-[52px] grad-text leading-none">31.6%</span>
                <span className="text-ink-soft text-[14px]">conversion</span>
              </div>
              {[["Entered",100],["Browsed",100],["Reached billing",33],["Purchased",32]].map(([k,w]) => (
                <div key={k as string} className="mb-2">
                  <div className="flex justify-between text-[12px] text-ink-soft mb-1">
                    <span>{k}</span><span>{w as number}%</span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.05)" }}>
                    <div className="h-full rounded-full grad-btn" style={{ width: `${w}%` }} />
                  </div>
                </div>
              ))}
            </div>
            {/* floating anomaly badge */}
            <div className="absolute -bottom-4 -left-4 card px-4 py-3 animate-float"
              style={{ animationDelay: "1.2s" }}>
              <div className="text-[11px] text-ink-faint">Anomaly detected</div>
              <div className="text-yellow-400 font-semibold text-[13px] mt-0.5">⚠ Queue depth 6</div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* features */}
      <section className="max-w-7xl mx-auto px-6 py-16 border-t border-line">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} {...rise(0.06 * i)}
              className="stat-card hover:shadow-glow transition-shadow duration-300">
              <div className="text-2xl mb-3">{f.icon}</div>
              <div className="font-semibold text-ink">{f.title}</div>
              <p className="text-[13px] text-ink-soft mt-2 leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* about */}
      <section id="about" className="max-w-7xl mx-auto px-6 py-16 border-t border-line">
        <motion.h2 {...rise(0)} className="font-display font-bold text-3xl mb-2">About</motion.h2>
        <motion.p {...rise(0.05)} className="text-ink-soft mb-8 max-w-2xl">
          Physical retail has always been a blind spot. This system changes that.
        </motion.p>
        <div className="grid md:grid-cols-3 gap-5">
          {[
            ["The Problem",
             "Online stores measure every click. Offline stores had nothing — no one knew how many people walked in, what they browsed, or why most left without buying."],
            ["What It Does",
             "A CV pipeline turns CCTV into structured events. A real-time API computes the conversion rate, a session funnel, zone heatmaps, anomalies and staff operations — grounded in the real Purplle POS data."],
            ["How It's Built",
             "YOLOv8 + ByteTrack detection in a container, FastAPI + Postgres + Redis intelligence service, a React ERP dashboard, docker compose for one-command deployment, Kubernetes manifests and GitHub Actions CI."],
          ].map(([t, d], i) => (
            <motion.div key={t} {...rise(0.07 * i)} className="card p-6">
              <div className="font-semibold text-ink mb-2">{t}</div>
              <p className="text-[13px] text-ink-soft leading-relaxed">{d}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* how to use */}
      <section id="how" className="max-w-7xl mx-auto px-6 py-16 border-t border-line">
        <motion.h2 {...rise(0)} className="font-display font-bold text-3xl mb-2">How it works</motion.h2>
        <motion.p {...rise(0.05)} className="text-ink-soft mb-8">Follow these steps to go from empty to insights.</motion.p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {HOW.map((h, i) => (
            <motion.div key={h.n} {...rise(0.07 * i)} className="card p-6">
              <div className="font-mono text-[11px] text-brand-2 mb-3 tracking-widest">{h.n}</div>
              <div className="font-semibold text-ink mb-2">{h.t}</div>
              <p className="text-[13px] text-ink-soft leading-relaxed">{h.d}</p>
            </motion.div>
          ))}
        </div>
        <div className="mt-10 flex justify-center">
          <Link to="/dashboard"
            className="grad-btn text-white px-8 py-3.5 rounded-xl font-semibold
              hover:scale-[1.02] transition-transform">
            Get started →
          </Link>
        </div>
      </section>

      <footer className="border-t border-line py-8 text-center text-[12px] text-ink-faint">
        Store Intelligence · Purplle Brigade Road ST1008 ·
        <a href="https://github.com/TechIT0104/store-intelligence" target="_blank" rel="noreferrer"
          className="text-ink-soft hover:text-ink ml-1">GitHub ↗</a>
      </footer>
    </div>
  );
}
