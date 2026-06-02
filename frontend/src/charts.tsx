import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { TimeSeries } from "./api";
import { Card } from "./components";

const axis = { stroke: "#6b7090", fontSize: 11 };

function TipBox({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line px-3 py-2 text-[12px]">
      <div className="text-ink-faint mb-1">{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-ink-soft">{p.name}</span>
          <span className="ml-auto font-semibold text-ink tnum">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

export function FootfallChart({ data }: { data?: TimeSeries }) {
  const series = data?.series ?? [];
  return (
    <Card delay={60}>
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">
        Footfall vs Sales · by hour
      </div>
      <div className="mt-4 h-[220px]">
        {series.length === 0 ? (
          <div className="h-full grid place-items-center text-ink-faint text-sm">no data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series} margin={{ left: -18, right: 6, top: 6 }}>
              <defs>
                <linearGradient id="gEntries" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.55} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gSales" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" />
              <XAxis dataKey="hour" tick={axis} tickLine={false} axisLine={false} />
              <YAxis tick={axis} tickLine={false} axisLine={false} width={34} />
              <Tooltip content={<TipBox />} />
              <Area type="monotone" dataKey="entries" name="footfall" stroke="#3b82f6"
                strokeWidth={2} fill="url(#gEntries)" />
              <Area type="monotone" dataKey="sales" name="sales" stroke="#10b981"
                strokeWidth={2} fill="url(#gSales)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}

export function ZoneBarChart({ data }: { data?: TimeSeries }) {
  const zones = data?.zones ?? [];
  const palette = ["#3b82f6", "#8b5cf6", "#06b6d4", "#06b6d4", "#10b981", "#f59e0b"];
  return (
    <Card delay={120}>
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">
        Zone Engagement · visits
      </div>
      <div className="mt-4 h-[220px]">
        {zones.length === 0 ? (
          <div className="h-full grid place-items-center text-ink-faint text-sm">no data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={zones} margin={{ left: -18, right: 6, top: 6 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" vertical={false} />
              <XAxis dataKey="zone" tick={axis} tickLine={false} axisLine={false} />
              <YAxis tick={axis} tickLine={false} axisLine={false} width={34} />
              <Tooltip content={<TipBox />} cursor={{ fill: "rgba(255,255,255,.04)" }} />
              <Bar dataKey="visits" radius={[8, 8, 0, 0]}>
                {zones.map((_, i) => <Cell key={i} fill={palette[i % palette.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}

export function RevenueBarChart({ staff }: { staff: { salesperson: string; revenue_inr: number }[] }) {
  const data = staff.map((s) => ({ name: (s.salesperson || "?").trim().split(" ")[0], revenue: s.revenue_inr }));
  return (
    <Card delay={60}>
      <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">
        Revenue by Employee (₹)
      </div>
      <div className="mt-4 h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: 4, right: 6, top: 6 }}>
            <defs>
              <linearGradient id="gRev" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#3b82f6" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" vertical={false} />
            <XAxis dataKey="name" tick={axis} tickLine={false} axisLine={false} />
            <YAxis tick={axis} tickLine={false} axisLine={false} width={48} />
            <Tooltip content={<TipBox />} cursor={{ fill: "rgba(255,255,255,.04)" }} />
            <Bar dataKey="revenue" name="revenue ₹" fill="url(#gRev)" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
