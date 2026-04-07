import fs from "node:fs";
import { spawn } from "node:child_process";
import { NextResponse } from "next/server";
import { GENERATED_POLICY, GENERATED_PROFILE, JOB_STATE_DIR, LIVE_RUN_LOG, LIVE_RUN_META, ROOT } from "@/lib/paths";

const allowedActions = new Set(["preview", "fill", "submit"]);

export async function POST(request: Request) {
  const payload = await request.json().catch(() => ({}));
  const userRequest =
    String(
      payload.request ||
        "Find remote or hybrid AI/backend software engineering roles at product-focused companies. Prioritize Python, LLM systems, applied AI, platform, or infra-heavy roles. Avoid obvious recruiting spam and junior-only roles. Prefer companies with clear application forms and salary transparency."
    ).trim();
  const applyLimit = Number(payload.applyLimit || 3);
  const maxJobs = Number(payload.maxJobs || 8);
  const requestedAction = String(payload.action || "fill");
  const action = allowedActions.has(requestedAction) ? requestedAction : "fill";

  fs.mkdirSync(JOB_STATE_DIR, { recursive: true });

  const command = [
    "bash",
    "-lc",
    [
      "bash scripts/prepare_openclaw_profile.sh",
      `bash run-job-agent.sh autopilot --profile "${GENERATED_PROFILE}" --policy "${GENERATED_POLICY}" --request "${userRequest.replace(/"/g, '\\"')}" --max-jobs ${maxJobs} --apply-limit ${applyLimit} --action ${action}`,
      `bash run-job-agent.sh tracker-export --profile "${GENERATED_PROFILE}" --policy "${GENERATED_POLICY}"`,
    ].join(" && "),
  ];

  const child = spawn(command[0], command.slice(1), {
    cwd: ROOT,
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, PYTHONPATH: `${ROOT}/src${process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""}` },
  });

  const output = fs.createWriteStream(LIVE_RUN_LOG, { flags: "w" });
  child.stdout.pipe(output);
  child.stderr.pipe(output);
  child.unref();

  fs.writeFileSync(
    LIVE_RUN_META,
    JSON.stringify(
      {
        pid: child.pid,
        startedAt: new Date().toISOString(),
        request: userRequest,
        applyLimit,
        maxJobs,
        action,
        profile: GENERATED_PROFILE,
      },
      null,
      2
    )
  );

  return NextResponse.json({ ok: true, pid: child.pid });
}
