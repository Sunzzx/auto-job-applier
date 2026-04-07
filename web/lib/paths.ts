import path from "node:path";

export const ROOT = path.resolve(process.cwd(), "..");
export const JOB_STATE_DIR = path.join(ROOT, ".job-agent");
export const LIVE_RUN_META = path.join(JOB_STATE_DIR, "live-run.json");
export const LIVE_RUN_LOG = path.join(JOB_STATE_DIR, "live-run.log");
export const TRACKER_PATH = path.join(JOB_STATE_DIR, "applications.md");
export const OPENCLAW_PROFILE = process.env.OPENCLAW_PROFILE_PATH || path.join(JOB_STATE_DIR, "job_profile.json");
export const GENERATED_PROFILE = path.join(ROOT, "examples", "profile.openclaw.yaml");
export const GENERATED_POLICY = path.join(ROOT, "examples", "policy.openclaw.yaml");
