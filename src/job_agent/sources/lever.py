from __future__ import annotations

import httpx

from job_agent.models import JobPosting, JobProfile
from job_agent.sources.base import BaseJobSource


class LeverSource(BaseJobSource):
    name = "lever"

    async def search(self, request: str, profile: JobProfile, limit: int) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for company in profile.target_companies.lever_companies:
                response = await client.get(f"https://api.lever.co/v0/postings/{company}?mode=json")
                response.raise_for_status()
                payload = response.json()
                for item in payload[:limit]:
                    categories = item.get("categories", {})
                    location = categories.get("location", "")
                    jobs.append(
                        JobPosting(
                            external_id=item.get("id", ""),
                            source=self.name,
                            title=item.get("text", ""),
                            company=company,
                            url=item.get("hostedUrl", ""),
                            location=location,
                            remote="remote" in location.lower(),
                            description=item.get("descriptionPlain", "") or "",
                            metadata={"team": categories.get("team", "")},
                        )
                    )
        return jobs
