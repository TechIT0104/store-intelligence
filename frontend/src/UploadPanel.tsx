import { useEffect, useRef, useState } from "react";
import { DetectJob, detect } from "./api";
import { Card } from "./components";

const STATE_LABEL: Record<string, string> = {
  queued: "Queued", detecting: "Running YOLOv8 + ByteTrack…",
  streaming: "Streaming events to the API…", done: "Done", error: "Error",
};

export function UploadPanel() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [cameras, setCameras] = useState<{ camera_id: string; role: string }[]>([]);
  const [camera, setCamera] = useState("CAM_FLOOR_02");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<DetectJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const poll = useRef<number | null>(null);

  useEffect(() => {
    detect.available().then(async (ok) => {
      setAvailable(ok);
      if (ok) {
        const c = await detect.cameras();
        setCameras(c.cameras ?? []);
        if (c.cameras?.length) setCamera(c.cameras[0].camera_id);
      }
    });
    return () => { if (poll.current) clearInterval(poll.current); };
  }, []);

  async function run() {
    if (!file) return;
    setBusy(true); setJob(null);
    try {
      const j = await detect.upload(file, camera);
      setJob(j);
      poll.current = window.setInterval(async () => {
        const s = await detect.job(j.job_id);
        setJob(s);
        if (s.state === "done" || s.state === "error") {
          if (poll.current) clearInterval(poll.current);
          setBusy(false);
        }
      }, 1500);
    } catch (e: any) {
      setJob({ job_id: "", state: "error", error: String(e?.message ?? e) });
      setBusy(false);
    }
  }

  if (available === false) {
    return (
      <Card delay={20}>
        <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">Upload &amp; Analyze</div>
        <div className="mt-3 text-sm text-ink-soft">
          The deployed detection service is offline. Start the full stack to enable
          live video analysis:
          <pre className="mt-2 bg-white/[0.05] rounded-lg p-3 text-[12px] overflow-auto">docker compose --profile full up --build</pre>
        </div>
      </Card>
    );
  }

  const pct = job ? (job.state === "done" ? 100
    : job.state === "streaming" ? 70 + Math.min(28, (job.events_posted ?? 0) / Math.max(1, job.events_total ?? 1) * 28)
    : job.state === "detecting" ? Math.min(65, 10 + (job.frames ?? 0) / 8)
    : 5) : 0;

  return (
    <Card delay={20}>
      <div className="flex items-center justify-between">
        <div className="text-[13px] font-medium tracking-wide text-ink-faint uppercase">
          Upload &amp; Analyze · deployed model
        </div>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-good/15 text-good">YOLOv8 live</span>
      </div>

      <label
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files?.[0] ?? null); }}
        className={`mt-3 flex flex-col items-center justify-center text-center rounded-2xl border-2
          border-dashed cursor-pointer py-7 transition-colors ${drag ? "border-brand bg-brand/5" : "border-line "}`}>
        <input type="file" accept="video/*" className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <div className="text-3xl">🎥</div>
        <div className="text-sm mt-1 text-ink">{file ? file.name : "Drop a CCTV clip or click to choose"}</div>
        <div className="text-[12px] text-ink-faint mt-0.5">mp4 · the model runs in-container</div>
      </label>

      <div className="mt-3 flex items-center gap-2">
        <select value={camera} onChange={(e) => setCamera(e.target.value)}
          className="flex-1 text-sm rounded-lg border border-line  bg-transparent px-3 py-2">
          {cameras.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.camera_id} · {c.role}</option>)}
        </select>
        <button onClick={run} disabled={!file || busy}
          className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium
            disabled:opacity-40 hover:bg-brand-2 transition-colors">
          {busy ? "Analyzing…" : "Run Detection"}
        </button>
      </div>

      {job && (
        <div className="mt-4">
          <div className="flex justify-between text-[12px] text-ink-soft mb-1">
            <span>{STATE_LABEL[job.state] ?? job.state}{job.frames ? ` · ${job.frames} frames` : ""}</span>
            <span>{job.events_posted ?? 0}/{job.events_total ?? "?"} events</span>
          </div>
          <div className="h-2 rounded-full bg-white/[0.05] overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500"
              style={{ width: `${pct}%`, background: job.state === "error" ? "#ff3b30" : "linear-gradient(90deg,#7c5cff,#34c759)" }} />
          </div>
          {job.state === "error" && <div className="text-[12px] text-crit mt-2">{job.error}</div>}
          {job.state === "done" && (
            <div className="mt-3 grid grid-cols-4 gap-2 text-center">
              {[["Entries", job.entry], ["Exits", job.exit], ["Visitors", job.visitors], ["Staff", job.staff]].map(
                ([k, v]) => (
                  <div key={k as string} className="rounded-xl bg-white/[0.05] py-2">
                    <div className="text-lg font-semibold tnum text-ink">{v as number}</div>
                    <div className="text-[11px] text-ink-faint">{k as string}</div>
                  </div>
                ))}
              {job.zones && Object.keys(job.zones).length > 0 && (
                <div className="col-span-4 text-[12px] text-ink-soft mt-1">
                  zones: {Object.entries(job.zones).map(([z, n]) => `${z} ${n}`).join(" · ")}
                </div>
              )}
              <div className="col-span-4 text-[12px] text-good mt-1">
                ✓ events flowed onto the live dashboard above
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
