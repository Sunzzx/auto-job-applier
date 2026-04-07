"use client";

import { useEffect, useMemo, useState } from "react";

type RunAction = "preview" | "fill" | "submit";

type TrackerRow = {
  index: string;
  date: string;
  company: string;
  role: string;
  score: string;
  status: string;
  source: string;
  link: string;
  notes: string;
};

type StatusPayload = {
  profileExists: boolean;
  trackerExists: boolean;
  trackerRows: TrackerRow[];
  runMeta: Record<string, unknown> | null;
  logTail: string;
};

const defaultRequest =
  "Find remote or hybrid AI/backend software engineering roles at product-focused companies. Prioritize Python, LLM systems, applied AI, platform, or infra-heavy roles. Avoid obvious recruiting spam and junior-only roles. Prefer companies with clear application forms and salary transparency.";

export function Dashboard({ initial }: { initial: StatusPayload }) {
  const [status, setStatus] = useState(initial);
  const [request, setRequest] = useState(defaultRequest);
  const [action, setAction] = useState<RunAction>("fill");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const timer = setInterval(async () => {
      const res = await fetch("/api/status", { cache: "no-store" });
      const next = (await res.json()) as StatusPayload;
      setStatus(next);
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  async function startRun() {
    setPending(true);
    try {
      await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request, action, maxJobs: 8, applyLimit: 3 }),
      });
      const res = await fetch("/api/status", { cache: "no-store" });
      setStatus(await res.json());
    } finally {
      setPending(false);
    }
  }

  const topRows = useMemo(() => status.trackerRows.slice(0, 12), [status.trackerRows]);

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Live career ops</p>
          <h1>Job search, shortlist, and submission progress in one place.</h1>
          <p className="lede">
            This dashboard is wired to your saved OpenClaw profile and the local job-agent automation. It polls live
            tracker state and background logs.
          </p>
        </div>
        <div className="heroCard">
          <div className="stat">
            <span>Profile</span>
            <strong>{status.profileExists ? "Loaded" : "Missing"}</strong>
          </div>
          <div className="stat">
            <span>Tracked roles</span>
            <strong>{status.trackerRows.length}</strong>
          </div>
          <div className="stat">
            <span>Latest mode</span>
            <strong>{String(status.runMeta?.action || "idle")}</strong>
          </div>
        </div>
      </section>

      <section className="grid">
        <article className="panel actionPanel">
          <div className="panelHeader">
            <h2>Run Autopilot</h2>
            <span>{pending ? "starting..." : "ready"}</span>
          </div>
          <textarea value={request} onChange={(event) => setRequest(event.target.value)} rows={7} />
          <label className="control">
            <span>Action mode</span>
            <select value={action} onChange={(event) => setAction(event.target.value as RunAction)}>
              <option value="preview">Preview only</option>
              <option value="fill">Fill without submit</option>
              <option value="submit">Submit on allowed domains</option>
            </select>
          </label>
          <button onClick={startRun} disabled={pending || !status.profileExists}>
            Start search + {action}
          </button>
          <p className="note">
            Starts a background run that converts your OpenClaw profile, searches openings, and then previews, fills,
            or submits depending on the selected mode.
          </p>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Background Run</h2>
            <span>{status.runMeta ? "active or recent" : "none yet"}</span>
          </div>
          <pre>{status.runMeta ? JSON.stringify(status.runMeta, null, 2) : "No run metadata yet."}</pre>
        </article>
      </section>

      <section className="grid">
        <article className="panel tablePanel">
          <div className="panelHeader">
            <h2>Top Tracker Rows</h2>
            <span>{status.trackerExists ? "synced" : "pending"}</span>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Company</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {topRows.map((row) => (
                  <tr key={`${row.index}-${row.company}-${row.role}`}>
                    <td>{row.index}</td>
                    <td>{row.company}</td>
                    <td>{row.role}</td>
                    <td>{row.status}</td>
                    <td>{row.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Live Log Tail</h2>
            <span>auto-refreshing</span>
          </div>
          <pre className="log">{status.logTail || "No logs yet."}</pre>
        </article>
      </section>
    </main>
  );
}
