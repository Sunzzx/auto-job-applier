# Job Agent

`job-agent` is a prompt-driven system that can:

- search multiple job sources
- score openings against your preferences
- track leads in SQLite
- preview, fill, and optionally submit applications in a browser

It is built to be broad and extensible, not magical. No tool can truly "scrape the entire internet," but this project gives you a strong autonomous base that can search public boards, company pages, and search engines, then apply where the workflow is machine-readable.

This version also borrows the strongest reusable ideas from [`santifer/career-ops`](https://github.com/santifer/career-ops): portal-scanner configuration, tracked-company conventions, and canonical tracker states.

## Features

- Prompt-based search requests such as "find remote backend roles in Europe with visa sponsorship"
- Career-Ops-compatible `portals.yml` strategy for tracked companies and query packs
- Pluggable sources for Greenhouse, Lever, RemoteOK, and web search discovery
- Structured profile and policy files
- Deterministic ranking with optional LLM-assisted scoring
- SQLite storage for leads, statuses, notes, and application actions
- Optional email notifications after each application attempt
- Markdown tracker export with canonical application states
- Playwright-based preview, fill, and guarded submit flows
- Safe stops for CAPTCHAs, OTP, missing answers, and ambiguous legal questions

## Quick Start

1. Create a virtual environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m playwright install chromium
```

2. Copy the example profile and policy:

```bash
cp examples/profile.example.yaml my-profile.yaml
cp examples/policy.example.yaml my-policy.yaml
cp examples/portals.example.yaml my-portals.yaml
```

3. Edit `my-profile.yaml` with your real details and point `my-policy.yaml` at `my-portals.yaml` if you want your own tracked companies.

4. If you want an email after every apply attempt, enable `notifications.enabled` in your policy and keep `notifications.backend: mail_app` on macOS. The recipient defaults to the profile email unless you override it.

5. Search for jobs:

```bash
bash run-job-agent.sh search \
  --profile my-profile.yaml \
  --policy my-policy.yaml \
  --request "Find remote software engineer roles in AI/ML startups, seniority mid to senior, visa-friendly, salary above 25 LPA"
```

6. Preview or fill an application:

```bash
bash run-job-agent.sh apply \
  --profile my-profile.yaml \
  --policy my-policy.yaml \
  --job-id <job-id-from-search> \
  --action preview
```

7. Run the full autopilot loop:

```bash
bash run-job-agent.sh autopilot \
  --profile my-profile.yaml \
  --policy my-policy.yaml \
  --request-file examples/prompts/remote-ai.txt \
  --max-jobs 25 \
  --apply-limit 5 \
  --action fill
```

## Commands

- `job-agent search`: collect and rank jobs, then store them in SQLite
- `job-agent list`: view stored jobs and statuses
- `job-agent apply`: preview, fill, or submit a selected job application
- `job-agent autopilot`: search, rank, shortlist, and start browser automation
- `job-agent tracker-export`: write a Career-Ops-style markdown tracker
- `job-agent verify`: verify tracker states against canonical labels

If the editable/package install is unreliable in an iCloud-backed folder, use `bash run-job-agent.sh ...` instead of the installed `job-agent` binary.

## Safety Model

- `preview`: opens and analyzes the page without changing it
- `fill`: fills known answers and uploads files, but does not submit
- `submit`: submits only if policy allows it and there are no unresolved questions

The system will stop when it hits:

- CAPTCHA or OTP
- account creation without explicit credentials
- free-form questions not covered by your profile/policy
- legal attestations that cannot be safely inferred

## Source Adapters

Current adapters:

- Career-Ops-style portals config with tracked companies and web queries
- Greenhouse boards
- Lever postings
- RemoteOK API
- DuckDuckGo HTML search for discovery

You can add more by implementing `BaseJobSource`.
