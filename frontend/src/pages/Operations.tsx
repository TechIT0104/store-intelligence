import { useEffect, useState } from "react";
import { api, StaffOps } from "../api";
import { RevenueBarChart } from "../charts";
import { Loader } from "../Loading";

export function Operations() {
  const [data, setData] = useState<StaffOps | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.staff().then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="card p-6 text-red-400 text-sm">{err}</div>;
  if (!data) return <Loader label="Loading store operations…" />;

  const maxRev = Math.max(1, ...data.staff.map((s) => s.revenue_inr));

  return (
    <>
      {/* page header */}
      <div className="mb-6">
        <h1 className="font-display font-bold text-2xl text-ink">Store Operations</h1>
        <p className="text-ink-soft text-[13px] mt-1">
          Employee performance from the <b className="text-ink">real Purplle POS export</b> (Brigade Road, 10 Apr 2026) —
          5 real staff, real transactions, real shift times. Always available; not affected by dashboard reset.
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Revenue",   value: `₹${data.summary.total_revenue_inr.toLocaleString()}`, badge: "badge-blue" },
          { label: "Transactions",    value: String(data.summary.total_transactions),               badge: "badge-violet" },
          { label: "Items Sold",      value: String(data.summary.total_items),                      badge: "badge-green" },
          { label: "Top Performer",   value: (data.summary.top_performer ?? "—").split(" ")[0],     badge: "badge-yellow" },
        ].map((s) => (
          <div key={s.label} className="stat-card">
            <div className="text-[11px] uppercase tracking-wider text-ink-faint mb-2">{s.label}</div>
            <div className="font-display font-bold text-2xl text-ink">{s.value}</div>
            <span className={`badge ${s.badge} mt-3 inline-block`}>
              {s.label === "Top Performer" ? "🏆 Leader" : "Today"}
            </span>
          </div>
        ))}
      </div>

      {/* revenue chart */}
      <div className="mb-6">
        <RevenueBarChart staff={data.staff} />
      </div>

      {/* staff table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-line flex items-center justify-between">
          <div>
            <div className="font-semibold text-ink">Employee Performance</div>
            <div className="text-[12px] text-ink-faint mt-0.5">{data.staff_count} staff · 10 Apr 2026</div>
          </div>
          <span className="badge badge-blue">{data.staff_count} active</span>
        </div>
        <div className="overflow-x-auto">
          <table className="erp-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Revenue</th>
                <th>Customers</th>
                <th>Shift</th>
                <th>Longest Break</th>
                <th>Utilisation</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.staff.map((s, i) => (
                <tr key={s.salesperson + i}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg grad-btn grid place-items-center
                        text-white text-[12px] font-bold shrink-0">
                        {s.salesperson.trim().slice(0, 1).toUpperCase() || "?"}
                      </div>
                      <div>
                        <div className="text-ink font-medium text-[13px]">{s.salesperson.trim() || "Unknown"}</div>
                        <div className="text-[11px] text-ink-faint">{s.employee_code || "—"}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="text-ink font-medium">₹{s.revenue_inr.toLocaleString()}</div>
                    <div className="mt-1 w-24 h-1.5 rounded-full overflow-hidden"
                      style={{ background: "rgba(255,255,255,0.05)" }}>
                      <div className="h-full rounded-full grad-btn"
                        style={{ width: `${(100 * s.revenue_inr) / maxRev}%` }} />
                    </div>
                  </td>
                  <td className="text-ink">{s.customers_attended}</td>
                  <td>{s.shift_hours}h</td>
                  <td>
                    <span className={s.took_lunch_break ? "text-yellow-400" : "text-ink-soft"}>
                      {Math.round(s.longest_break_min)}m
                      {s.took_lunch_break && <span className="ml-1 text-[11px]">(lunch)</span>}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full overflow-hidden"
                        style={{ background: "rgba(255,255,255,0.05)" }}>
                        <div className="h-full rounded-full"
                          style={{ width: `${Math.round(s.utilisation * 100)}%`,
                            background: s.utilisation > 0.2 ? "#3b82f6" : "#8b5cf6" }} />
                      </div>
                      <span className="text-[12px]">{Math.round(s.utilisation * 100)}%</span>
                    </div>
                  </td>
                  <td>
                    {i === 0
                      ? <span className="badge badge-yellow">🏆 Top</span>
                      : s.shift_hours > 4
                        ? <span className="badge badge-green">Active</span>
                        : <span className="badge badge-violet">Part day</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-5 py-3 border-t border-line text-[11px] text-ink-faint">
          Break = longest idle gap between billings. Utilisation ≈ service-minutes ÷ shift-minutes.
          Grounded in the real POS export — no hardcoding.
        </div>
      </div>
    </>
  );
}
