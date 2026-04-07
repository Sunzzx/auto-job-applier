from __future__ import annotations

import httpx

from job_agent.models import JobPosting, JobProfile
from job_agent.sources.base import BaseJobSource


class GreenhouseSource(BaseJobSource):
    name = "greenhouse"

    async def search(self, request: str, profile: JobProfile, limit: int) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for board in profile.target_companies.greenhouse_boards:
                response = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
                response.raise_for_status()
                payload = response.json()
                for item in payload.get("jobs", [])[:limit]:
                    jobs.append(
                        JobPosting(
                            external_id=str(item["id"]),
                            source=self.name,
                            title=item.get("title", ""),
                            company=board,
                            url=item.get("absolute_url", ""),
                            location=(item.get("location") or {}).get("name", ""),
                            remote="remote" in ((item.get("location") or {}).get("name", "").lower()),
                            metadata={"board": board},
                        )
                    )
        return jobs
