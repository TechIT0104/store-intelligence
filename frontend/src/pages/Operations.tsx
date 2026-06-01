import { useEffect, useState } from "react";
import { api, StaffOps } from "../api";
import { Card } from "../components";
import { RevenueBarChart } from "../charts";
import { Loader } from "../Loading";
import { useCountUp } from "../hooks";

function Stat({ label, value, suffix = "" }: { label: string; value: number; suffix?: string }) {
  const v = useCountUp(value);
  return (
    <Card>
      <div className="text-[12px] uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="font-display font-bold text-4xl mt-2 grad-text">
        {Number.isInteger(value) ? Math.round(v) : v.toFixed(1)}{suffix}
      </div>
    </Card>
  );
}

export function Operations() {
  const [data, setData] = useState<StaffOps | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.staff().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <Card><div className="text-crit text-sm">Failed to load staff data: {err}</div></Card>;
  if (!data) return <Loader label="Reconstructing the staff day…" />;

  const maxRev = Math.max(1, ...data.staff.map((s) => s.revenue_inr));

  return (
    <>
      <div className="mb-6">
        <h1 className="font-display font-bold text-3xl tracking-tight">Store Operations</h1>
        <p className="text-ink-soft mt-1">
          Each employee's working day reconstructed from the real POS — sales handled,
          shift span, breaks and utilisation. Detection flags staff on the floor; POS
          attributes the work.
        </p>
      </div>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Revenue (₹)" value={data.summary.total_revenue_inr} />
        <Stat label="Transactions" value={data.summary.total_transactions} />
        <Stat label="Items Sold" value={data.summary.total_items} />
        <Stat label="Avg Utilisation" value={(data.summary.avg_utilisation ?? 0) * 100} suffix="%" />
      </section>

      <section className="mt-4">
        <RevenueBarChart staff={data.staff} />
      </section>

      <section className="mt-4 space-y-3">
        {data.staff.map((s, i) => (
          <Card key={s.salesperson + i} delay={i * 50} className="!p-5">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="w-11 h-11 rounded-2xl grad-btn flex items-center justify-center font-bold text-white">
                {s.salesperson.trim().slice(0, 1).toUpperCase() || "?"}
              </div>
              <div className="min-w-[160px]">
                <div className="font-semibold flex items-center gap-2">
                  {s.salesperson.trim() || "Unknown"}
                  {i === 0 && <span className="chip text-good border-good/30">top performer</span>}
                </div>
                <div className="text-[12px] text-ink-faint">{s.employee_code || "—"}</div>
              </div>

              <div className="flex-1 min-w-[200px]">
                <div className="flex justify-between text-[12px] text-ink-soft mb-1">
                  <span>₹{s.revenue_inr.toLocaleString()}</span>
                  <span>{s.transactions} sales · {s.items_sold} items</span>
                </div>
                <div className="h-2.5 rounded-full bg-white/[0.05] overflow-hidden">
                  <div className="h-full grad-btn transition-all duration-700"
                    style={{ width: `${(100 * s.revenue_inr) / maxRev}%` }} />
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4 text-center">
                <Mini label="customers" value={s.customers_attended} />
                <Mini label="shift" value={`${s.shift_hours}h`} />
                <Mini label="break" value={`${Math.round(s.longest_break_min)}m`}
                  tone={s.took_lunch_break ? "warn" : undefined} />
                <Mini label="util" value={`${Math.round(s.utilisation * 100)}%`} />
              </div>
            </div>
          </Card>
        ))}
      </section>

      <footer className="mt-8 text-[12px] text-ink-faint text-center">
        Break = longest idle gap between a salesperson's billings (lunch proxy). Utilisation
        ≈ service-minutes ÷ shift-minutes. Grounded in the real POS export — no hardcoding.
      </footer>
    </>
  );
}

function Mini({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div>
      <div className={`font-semibold tnum ${tone === "warn" ? "text-warn" : "text-ink"}`}>{value}</div>
      <div className="text-[11px] text-ink-faint">{label}</div>
    </div>
  );
}
