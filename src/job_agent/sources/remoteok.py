from __future__ import annotations

import httpx

from job_agent.models import JobPosting, JobProfile
from job_agent.sources.base import BaseJobSource


class RemoteOKSource(BaseJobSource):
    name = "remoteok"

    async def search(self, request: str, profile: JobProfile, limit: int) -> list[JobPosting]:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "job-agent/0.1"}) as client:
            response = await client.get("https://remoteok.com/api")
            response.raise_for_status()
            payload = response.json()
        jobs: list[JobPosting] = []
        for item in payload[1 : limit + 1]:
            if not isinstance(item, dict):
                continue
            tags = item.get("tags", []) or []
            jobs.append(
                JobPosting(
                    external_id=str(item.get("id", "")),
                    source=self.name,
                    title=item.get("position", ""),
                    company=item.get("company", ""),
                    url=item.get("url", ""),
                    location="Remote",
                    remote=True,
                    description="\n".join(tags),
                    compensation=item.get("salary_min") and f"{item.get('salary_min')} - {item.get('salary_max')}" or "",
                    metadata={"tags": tags},
                )
            )
        return jobs
