import { motion } from "framer-motion";
import { Link } from "react-router-dom";

const features = [
  { icon: "🎥", t: "Detection", d: "YOLOv8 + ByteTrack in a container" },
  { icon: "🧭", t: "Re-ID", d: "Re-entry & cross-camera dedup" },
  { icon: "🧠", t: "Staff AI", d: "Access + behaviour + VLM" },
  { icon: "📈", t: "Conversion", d: "POS-correlated, real-time" },
];

const rise = (d: number) => ({
  initial: { opacity: 0, y: 20 }, animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, delay: d, ease: [0.2, 0.7, 0.2, 1] as const },
});

export function Landing() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="absolute inset-0 grid-bg pointer-events-none" />
      {/* floating glows */}
      <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-brand/20 blur-3xl animate-float" />
      <div className="absolute top-40 -right-24 w-96 h-96 rounded-full bg-brand-3/20 blur-3xl animate-float"
           style={{ animationDelay: "1.5s" }} />

      <header className="relative max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl grad-btn" />
          <span className="font-display font-bold text-lg">Store Intelligence</span>
        </div>
        <Link to="/dashboard" className="chip text-ink-soft hover:text-ink">Open app →</Link>
      </header>

      <section className="relative max-w-7xl mx-auto px-6 pt-16 pb-24 grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <motion.div {...rise(0)} className="inline-flex items-center gap-2 chip text-ink-soft mb-6">
            <span className="w-2 h-2 rounded-full bg-good animate-pulse" /> Purplle · Brigade Road · ST1008
          </motion.div>
          <motion.h1 {...rise(0.08)} className="font-display font-extrabold leading-[1.05] text-5xl sm:text-6xl">
            Turn raw <span className="grad-text">CCTV</span><br />into store intelligence
          </motion.h1>
          <motion.p {...rise(0.16)} className="mt-6 text-ink-soft text-lg max-w-xl">
            A computer-vision pipeline that detects shoppers, tracks journeys, separates
            staff, and computes the offline <b className="text-ink">conversion rate</b> —
            correlated with real POS sales, in real time.
          </motion.p>
          <motion.div {...rise(0.24)} className="mt-9 flex flex-wrap gap-3">
            <Link to="/dashboard"
              className="grad-btn text-white px-6 py-3 rounded-2xl font-semibold hover:scale-[1.03] transition-transform">
              Launch Dashboard →
            </Link>
            <Link to="/operations"
              className="px-6 py-3 rounded-2xl font-semibold glass hover:bg-white/10 transition-colors">
              Store Operations
            </Link>
          </motion.div>
          <motion.div {...rise(0.32)} className="mt-10 flex gap-8">
            {[["31.6%", "conversion"], ["24", "purchases (POS)"], ["5", "cameras"], ["6", "staff tracked"]].map(
              ([v, l]) => (
                <div key={l}>
                  <div className="font-display font-bold text-2xl grad-text">{v}</div>
                  <div className="text-[12px] text-ink-faint">{l}</div>
                </div>
              ))}
          </motion.div>
        </div>

        {/* floating preview card */}
        <motion.div {...rise(0.2)} className="relative">
          <div className="card p-6 animate-float">
            <div className="flex items-center justify-between">
              <span className="text-[12px] text-ink-faint uppercase tracking-wide">Live · Today</span>
              <span className="chip text-good border-good/30">▲ healthy feed</span>
            </div>
            <div className="mt-4 flex items-end gap-2">
              <span className="font-display font-extrabold text-6xl grad-text">31.6%</span>
              <span className="text-ink-soft mb-2">conversion</span>
            </div>
            <div className="mt-5 space-y-2">
              {[["Entered", 100], ["Browsed", 100], ["Billing", 33], ["Purchased", 32]].map(([k, w]) => (
                <div key={k as string}>
                  <div className="flex justify-between text-[12px] text-ink-soft"><span>{k}</span><span>{w as number}%</span></div>
                  <div className="h-2 rounded-full bg-white/[0.05] overflow-hidden">
                    <div className="h-full grad-btn" style={{ width: `${w}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="absolute -bottom-6 -left-6 card px-4 py-3 animate-float" style={{ animationDelay: "1s" }}>
            <div className="text-[12px] text-ink-faint">Queue spike</div>
            <div className="text-warn font-semibold text-sm">WARN · depth 6</div>
          </div>
        </motion.div>
      </section>

      {/* feature row */}
      <section className="relative max-w-7xl mx-auto px-6 pb-24 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {features.map((f, i) => (
          <motion.div key={f.t} {...rise(0.1 * i)} className="card p-5 hover:shadow-glow transition-shadow">
            <div className="text-2xl">{f.icon}</div>
            <div className="font-semibold mt-2">{f.t}</div>
            <div className="text-[13px] text-ink-soft mt-1">{f.d}</div>
          </motion.div>
        ))}
      </section>
    </div>
  );
}
