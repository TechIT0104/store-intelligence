import { NavLink, Outlet, Link } from "react-router-dom";

const NAV = [
  { to: "/dashboard", icon: "▦", label: "Dashboard" },
  { to: "/operations", icon: "◈", label: "Store Ops" },
];

function SideItem({ to, icon, label }: { to: string; icon: string; label: string }) {
  return (
    <NavLink to={to} className={({ isActive }) =>
      `nav-item ${isActive ? "nav-item-active" : ""}`}>
      <span className="text-[18px] w-5 text-center leading-none">{icon}</span>
      <span>{label}</span>
    </NavLink>
  );
}

export function Layout() {
  return (
    <div className="flex min-h-screen" style={{ background: "#060d1a" }}>
      {/* sidebar */}
      <aside className="w-60 shrink-0 flex flex-col border-r border-line animate-slide-in"
        style={{ background: "#080f1e" }}>
        <Link to="/" className="flex items-center gap-3 px-5 h-16 border-b border-line shrink-0">
          <div className="w-8 h-8 rounded-lg grad-btn flex items-center justify-center">
            <span className="text-white text-[14px] font-bold">SI</span>
          </div>
          <div>
            <div className="font-display font-bold text-[14px] leading-none text-ink">Store Intel</div>
            <div className="text-[10px] text-ink-faint mt-0.5">Brigade Road · ST1008</div>
          </div>
        </Link>
        <nav className="flex-1 px-3 py-4 space-y-1">
          <div className="text-[10px] uppercase tracking-widest text-ink-faint px-3 mb-2">Main</div>
          {NAV.map((n) => <SideItem key={n.to} {...n} />)}
          <div className="text-[10px] uppercase tracking-widest text-ink-faint px-3 mb-2 mt-6">Resources</div>
          <a href="https://github.com/TechIT0104/store-intelligence" target="_blank" rel="noreferrer"
            className="nav-item">
            <span className="text-[18px] w-5 text-center leading-none">⌥</span>
            <span>GitHub</span>
          </a>
        </nav>
        <div className="px-4 py-4 border-t border-line">
          <div className="flex items-center gap-2 text-[12px]">
            <span className="w-2 h-2 rounded-full animate-pulseglow" style={{ background: "#10b981" }} />
            <span className="text-ink-soft">API online</span>
          </div>
          <div className="text-[11px] text-ink-faint mt-0.5">Detection · Redis · Postgres</div>
        </div>
      </aside>

      {/* main area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b border-line flex items-center justify-between px-6 shrink-0"
          style={{ background: "#080f1e" }}>
          <div className="text-[13px] text-ink-soft">Purplle Store Intelligence System</div>
          <div className="flex items-center gap-3 text-[12px]">
            <span className="chip text-ink-faint">10 Apr 2026</span>
            <span className="chip text-ink-faint">ST1008</span>
          </div>
        </header>
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
