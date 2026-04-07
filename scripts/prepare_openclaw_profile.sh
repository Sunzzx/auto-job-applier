#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/examples"

python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
source = Path(os.environ.get("OPENCLAW_PROFILE_PATH", root / ".job-agent" / "job_profile.json"))
profile = json.loads(source.read_text(encoding="utf-8"))

skills = profile.get("skills", [])
identity = {
    "identity": {
        "full_name": profile["full_name"],
        "email": profile["email"],
        "phone": profile["phone"],
        "location": profile["location"],
        "linkedin": profile.get("linkedin_url", ""),
        "github": profile.get("github_url", ""),
        "portfolio": profile.get("portfolio_url", ""),
        "website": profile.get("portfolio_url", ""),
    },
    "work_preferences": {
        "titles": ["AI Engineer", "Backend Engineer", "Software Engineer", "ML Engineer", "Data Scientist"],
        "keywords": skills[:18],
        "preferred_locations": ["Remote", "Bangalore", "New Delhi", "India"],
        "remote_only": False,
        "visa_sponsorship_required": bool(profile.get("requires_sponsorship", False)),
        "minimum_salary": {"currency": "INR", "amount": 1200000},
        "excluded_keywords": ["sales", "commission only", "android", "ios"],
        "target_seniority": ["entry", "junior", "mid"],
    },
    "materials": {
        "resume_path": profile["resume_path"],
        "cover_letter_path": "",
        "additional_files": [],
    },
    "employment": {
        "years_of_experience": int(profile.get("years_experience") or 0),
        "current_title": "Student / Software Developer",
        "skills": skills,
        "industries": ["AI", "Software", "Data"],
        "work_authorization": {"india": bool(profile.get("authorized_to_work", True))},
    },
    "education": {
        "degree": profile.get("education", {}).get("degree", ""),
        "field": "Computer Science and Data Analytics",
        "institution": profile.get("education", {}).get("institution", ""),
        "graduation_year": profile.get("education", {}).get("end_year"),
    },
    "answers": {
        "sponsorship_required": "Yes" if profile.get("requires_sponsorship") else "No",
        "willing_to_relocate": "Yes" if profile.get("willing_to_relocate") else "No",
        "years_of_experience": str(profile.get("years_experience") or 0),
        "linkedin": profile.get("linkedin_url", ""),
        "github": profile.get("github_url", ""),
    },
    "target_companies": {
        "greenhouse_boards": ["anthropic", "intercom", "openai"],
        "lever_companies": ["scaleai", "notion"]
    },
    "search": {
        "default_queries": [
            "site:boards.greenhouse.io OR site:job-boards.greenhouse.io AI engineer remote India",
            "site:jobs.lever.co backend engineer remote India",
            "site:jobs.ashbyhq.com software engineer ai remote"
        ]
    },
}

policy = {
    "database_path": ".job-agent/job_agent.db",
    "artifacts_dir": ".job-agent/artifacts",
    "tracker_markdown_path": ".job-agent/applications.md",
    "portals_config_path": "examples/portals.example.yaml",
    "states_config_path": "templates/states.yml",
    "submit_mode": "guarded",
    "max_search_results_per_source": 30,
    "max_apply_per_run": 3,
    "allow_domains_for_submit": ["greenhouse.io", "job-boards.greenhouse.io", "boards.greenhouse.io", "jobs.lever.co"],
    "deny_domains": ["indeed.com", "linkedin.com"],
    "stop_on_missing_answers": True,
    "headless_browser": True,
    "auto_upload_resume": True,
    "search": {
        "use_career_ops_portals": True,
        "use_greenhouse": True,
        "use_lever": True,
        "use_remoteok": True,
        "use_web_search": True,
    },
}

def dump_yaml(data, indent=0):
    lines = []
    prefix = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and not value:
                lines.append(f"{prefix}{key}: {{}}")
            elif isinstance(value, list) and not value:
                lines.append(f"{prefix}{key}: []")
            elif isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(dump_yaml(value, indent + 1))
            else:
                serialized = json.dumps(value) if isinstance(value, str) else str(value).lower() if isinstance(value, bool) else str(value)
                lines.append(f"{prefix}{key}: {serialized}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(dump_yaml(item, indent + 1))
            else:
                serialized = json.dumps(item) if isinstance(item, str) else str(item)
                lines.append(f"{prefix}- {serialized}")
    return lines

(root / "examples" / "profile.openclaw.yaml").write_text("\n".join(dump_yaml(identity)) + "\n", encoding="utf-8")
(root / "examples" / "policy.openclaw.yaml").write_text("\n".join(dump_yaml(policy)) + "\n", encoding="utf-8")
print("wrote openclaw profile + policy")
PY
