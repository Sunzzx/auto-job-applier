from __future__ import annotations

from pathlib import Path

from job_agent.models import TrackerStates
from job_agent.storage import JobStore


STATUS_MAP = {
    "discovered": "Evaluated",
    "shortlisted": "Evaluated",
    "previewed": "Evaluated",
    "filled": "Evaluated",
    "submitted": "Applied",
    "blocked": "Evaluated",
    "skipped": "SKIP",
}


class MarkdownTracker:
    def __init__(self, path: str, states: TrackerStates) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.states = states

    def export(self, store: JobStore) -> None:
        rows = store.list_jobs_full()
        header = [
            "# Job Agent Tracker",
            "",
            "| # | Date | Company | Role | Score | Status | Source | Link | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        body = []
        for idx, row in enumerate(rows, start=1):
            body.append(
                "| {idx} | {date} | {company} | {title} | {score:.2f}/100 | {status} | {source} | [job]({url}) | {dedupe} |".format(
                    idx=idx,
                    date=(row["created_at"] or "")[:10],
                    company=self._clean(row["company"]),
                    title=self._clean(row["title"]),
                    score=row["score"] or 0,
                    status=self._map_status(row["status"]),
                    source=self._clean(row["source"]),
                    url=row["url"],
                    dedupe=self._clean(row["dedupe_key"]),
                )
            )
        self.path.write_text("\n".join(header + body) + "\n", encoding="utf-8")

    def verify(self) -> list[str]:
        if not self.path.exists():
            return [f"Tracker file not found: {self.path}"]
        content = self.path.read_text(encoding="utf-8")
        issues: list[str] = []
        allowed = {state.label.lower() for state in self.states.states} or {
            "evaluated",
            "applied",
            "responded",
            "interview",
            "offer",
            "rejected",
            "discarded",
            "skip",
        }
        for line in content.splitlines():
            if not line.startswith("|") or line.startswith("|---"):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 10 or parts[1] == "#":
                continue
            status = parts[6].lower()
            if status not in allowed:
                issues.append(f"Non-canonical status: {parts[6]}")
        return issues

    def _map_status(self, status: str) -> str:
        target = STATUS_MAP.get(status, "Evaluated")
        labels = {state.label.lower(): state.label for state in self.states.states}
        return labels.get(target.lower(), target)

    def _clean(self, value: str) -> str:
        return value.replace("|", "/")
