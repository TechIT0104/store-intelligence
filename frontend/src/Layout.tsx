import { NavLink, Outlet, Link } from "react-router-dom";

const link = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-full text-[13px] font-medium transition-colors ${
    isActive ? "bg-white/10 text-ink" : "text-ink-soft hover:text-ink hover:bg-white/5"}`;

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 glass border-b border-line">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl grad-btn" />
            <div>
              <div className="font-display text-[15px] font-bold leading-none">Store Intelligence</div>
              <div className="text-[12px] text-ink-faint mt-0.5">Brigade Road · ST1008</div>
            </div>
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink to="/dashboard" className={link}>Dashboard</NavLink>
            <NavLink to="/operations" className={link}>Store Ops</NavLink>
            <a href="https://github.com/TechIT0104/store-intelligence" target="_blank"
               rel="noreferrer" className="ml-2 chip text-ink-soft hover:text-ink">GitHub ↗</a>
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
