import fs from "node:fs";
import { LIVE_RUN_LOG, LIVE_RUN_META, OPENCLAW_PROFILE, TRACKER_PATH } from "./paths";

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

export type DashboardStatus = {
  profileExists: boolean;
  trackerExists: boolean;
  trackerRows: TrackerRow[];
  runMeta: Record<string, unknown> | null;
  logTail: string;
};

function tail(text: string, lineCount = 80) {
  const lines = text.split("\n");
  return lines.slice(-lineCount).join("\n");
}

function parseTracker(markdown: string): TrackerRow[] {
  return markdown
    .split("\n")
    .filter((line) => line.startsWith("|") && !line.startsWith("|---") && !line.includes("| # |"))
    .map((line) => line.split("|").map((part) => part.trim()))
    .filter((parts) => parts.length >= 11)
    .map((parts) => ({
      index: parts[1],
      date: parts[2],
      company: parts[3],
      role: parts[4],
      score: parts[5],
      status: parts[6],
      source: parts[7],
      link: parts[8],
      notes: parts[9],
    }));
}

export function readDashboardStatus(): DashboardStatus {
  const profileExists = fs.existsSync(OPENCLAW_PROFILE);
  const trackerExists = fs.existsSync(TRACKER_PATH);
  const trackerRows = trackerExists ? parseTracker(fs.readFileSync(TRACKER_PATH, "utf8")) : [];
  const runMeta = fs.existsSync(LIVE_RUN_META)
    ? JSON.parse(fs.readFileSync(LIVE_RUN_META, "utf8"))
    : null;
  const logTail = fs.existsSync(LIVE_RUN_LOG) ? tail(fs.readFileSync(LIVE_RUN_LOG, "utf8")) : "";

  return {
    profileExists,
    trackerExists,
    trackerRows,
    runMeta,
    logTail,
  };
}
