from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from job_agent.models import ApplyOutcome, JobPosting, JobStatus, RankedJob


class JobStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    dedupe_key TEXT PRIMARY KEY,
                    external_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    location TEXT,
                    remote INTEGER NOT NULL DEFAULT 0,
                    description TEXT,
                    compensation TEXT,
                    metadata_json TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0,
                    reasons_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'discovered',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dedupe_key TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    job_url TEXT,
                    domain TEXT,
                    blocker_type TEXT,
                    blocker_signals_json TEXT NOT NULL DEFAULT '[]',
                    notes_json TEXT NOT NULL,
                    screenshot_paths_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self._ensure_application_columns(conn)

    def _ensure_application_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(applications)").fetchall()
        }
        required_columns = {
            "job_url": "TEXT",
            "domain": "TEXT",
            "blocker_type": "TEXT",
            "blocker_signals_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column_name, column_type in required_columns.items():
            if column_name not in existing:
                conn.execute(f"ALTER TABLE applications ADD COLUMN {column_name} {column_type}")

    def upsert_ranked_job(self, ranked: RankedJob) -> None:
        job = ranked.job
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    dedupe_key, external_id, source, company, title, url, location,
                    remote, description, compensation, metadata_json, score, reasons_json, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    company=excluded.company,
                    title=excluded.title,
                    url=excluded.url,
                    location=excluded.location,
                    remote=excluded.remote,
                    description=excluded.description,
                    compensation=excluded.compensation,
                    metadata_json=excluded.metadata_json,
                    score=excluded.score,
                    reasons_json=excluded.reasons_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    job.dedupe_key(),
                    job.external_id,
                    job.source,
                    job.company,
                    job.title,
                    str(job.url),
                    job.location,
                    1 if job.remote else 0,
                    job.description,
                    job.compensation,
                    json.dumps(job.metadata),
                    ranked.score,
                    json.dumps(ranked.reasons),
                    JobStatus.discovered.value,
                ),
            )

    def record_apply_outcome(self, outcome: ApplyOutcome) -> None:
        domain = urlparse(str(outcome.job.url)).netloc.lower()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE dedupe_key = ?
                """,
                (outcome.status.value, outcome.job.dedupe_key()),
            )
            conn.execute(
                """
                INSERT INTO applications (
                    dedupe_key, action, status, job_url, domain, blocker_type,
                    blocker_signals_json, notes_json, screenshot_paths_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.job.dedupe_key(),
                    outcome.action.value,
                    outcome.status.value,
                    str(outcome.job.url),
                    domain,
                    outcome.blocker_type,
                    json.dumps(outcome.blocker_signals),
                    json.dumps(outcome.notes),
                    json.dumps(outcome.screenshot_paths),
                ),
            )

    def get_recently_blocked_domains(self, cooldown_hours: int = 72) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT domain
                FROM applications
                WHERE status = 'blocked'
                  AND domain IS NOT NULL
                  AND domain != ''
                  AND created_at >= datetime('now', ?)
                  AND (
                    blocker_type IN ('captcha', 'otp', 'botwall')
                    OR blocker_type IS NULL
                  )
                """,
                (f"-{max(1, cooldown_hours)} hours",),
            ).fetchall()
        return {row[0] for row in rows if row[0]}

    def list_jobs(self, limit: int = 20) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT company, title, source, url, score, status
                FROM jobs
                ORDER BY score DESC, updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "company": row[0],
                "title": row[1],
                "source": row[2],
                "url": row[3],
                "score": row[4],
                "status": row[5],
            }
            for row in rows
        ]

    def list_jobs_full(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT dedupe_key, company, title, source, url, score, status, created_at
                FROM jobs
                ORDER BY score DESC, updated_at DESC
                """
            ).fetchall()
        return [
            {
                "dedupe_key": row[0],
                "company": row[1],
                "title": row[2],
                "source": row[3],
                "url": row[4],
                "score": row[5],
                "status": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    def get_job(self, dedupe_key: str) -> JobPosting | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT external_id, source, title, company, url, location, remote, description, compensation, metadata_json
                FROM jobs
                WHERE dedupe_key = ?
                """,
                (dedupe_key,),
            ).fetchone()
        if row is None:
            return None
        return JobPosting(
            external_id=row[0],
            source=row[1],
            title=row[2],
            company=row[3],
            url=row[4],
            location=row[5] or "",
            remote=bool(row[6]),
            description=row[7] or "",
            compensation=row[8] or "",
            metadata=json.loads(row[9]),
        )

    def get_job_status(self, dedupe_key: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT status
                FROM jobs
                WHERE dedupe_key = ?
                """,
                (dedupe_key,),
            ).fetchone()
        return row[0] if row else None
