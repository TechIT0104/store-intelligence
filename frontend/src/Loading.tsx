export function Loader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 animate-fade-up">
      <div className="relative w-14 h-14">
        <div className="absolute inset-0 rounded-full border-2 border-white/10" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-brand
          border-r-brand-2 animate-spinslow" />
        <div className="absolute inset-2 rounded-full grad-btn opacity-20 animate-pulseglow" />
      </div>
      <div className="text-[13px] text-ink-soft">{label}</div>
    </div>
  );
}

// shimmer skeleton block for buffering states
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`rounded-2xl bg-surface2/40 overflow-hidden relative ${className}`}>
      <div className="absolute inset-0 animate-shimmer"
        style={{ background: "linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent)",
                 backgroundSize: "200% 100%" }} />
    </div>
  );
}
