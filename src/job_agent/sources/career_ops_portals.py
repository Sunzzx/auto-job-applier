from __future__ import annotations

import httpx

from job_agent.models import CareerOpsPortals, JobPosting, JobProfile, TrackedCompany
from job_agent.sources.base import BaseJobSource
from job_agent.sources.web_search import WebSearchSource


class CareerOpsPortalSource(BaseJobSource):
    name = "career_ops_portals"

    def __init__(self, portals: CareerOpsPortals) -> None:
        self.portals = portals
        self.web_search = WebSearchSource()

    async def search(self, request: str, profile: JobProfile, limit: int) -> list[JobPosting]:
        del request, profile
        jobs: list[JobPosting] = []

        for company in self.portals.tracked_companies:
            if not company.enabled:
                continue
            jobs.extend(await self._scan_company(company, limit=max(1, limit - len(jobs))))
            if len(jobs) >= limit:
                return self._filter_titles(jobs[:limit])

        for query in self.portals.search_queries:
            if not query.enabled:
                continue
            jobs.extend(await self.web_search.search_query(query.query, limit=max(1, limit - len(jobs))))
            if len(jobs) >= limit:
                break

        return self._filter_titles(jobs[:limit])

    async def _scan_company(self, company: TrackedCompany, limit: int) -> list[JobPosting]:
        if company.api and "greenhouse" in company.api:
            return await self._scan_greenhouse_api(company, limit)
        if company.scan_query:
            return await self.web_search.search_query(company.scan_query, limit=limit, company_hint=company.name)
        if "jobs.lever.co" in company.careers_url:
            slug = company.careers_url.rstrip("/").split("/")[-1]
            return await self._scan_lever_company(company.name, slug, limit)
        return []

    async def _scan_greenhouse_api(self, company: TrackedCompany, limit: int) -> list[JobPosting]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(company.api)
            response.raise_for_status()
            payload = response.json()
        jobs: list[JobPosting] = []
        for item in payload.get("jobs", [])[:limit]:
            location = (item.get("location") or {}).get("name", "")
            jobs.append(
                JobPosting(
                    external_id=str(item["id"]),
                    source=self.name,
                    title=item.get("title", ""),
                    company=company.name,
                    url=item.get("absolute_url", ""),
                    location=location,
                    remote="remote" in location.lower(),
                    metadata={"origin": "career-ops", "notes": company.notes or "", "company_url": company.careers_url},
                )
            )
        return jobs

    async def _scan_lever_company(self, company_name: str, slug: str, limit: int) -> list[JobPosting]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            response.raise_for_status()
            payload = response.json()
        jobs: list[JobPosting] = []
        for item in payload[:limit]:
            location = (item.get("categories") or {}).get("location", "")
            jobs.append(
                JobPosting(
                    external_id=item.get("id", ""),
                    source=self.name,
                    title=item.get("text", ""),
                    company=company_name,
                    url=item.get("hostedUrl", ""),
                    location=location,
                    remote="remote" in location.lower(),
                    description=item.get("descriptionPlain", "") or "",
                    metadata={"origin": "career-ops", "company_slug": slug},
                )
            )
        return jobs

    def _filter_titles(self, jobs: list[JobPosting]) -> list[JobPosting]:
        positives = [item.lower() for item in self.portals.title_filter.positive]
        negatives = [item.lower() for item in self.portals.title_filter.negative]
        seniority = [item.lower() for item in self.portals.title_filter.seniority_boost]
        filtered: list[JobPosting] = []
        for job in jobs:
            title = job.title.lower()
            if positives and not any(word in title for word in positives):
                continue
            if any(word in title for word in negatives):
                continue
            if any(word in title for word in seniority):
                job.metadata["career_ops_seniority_boost"] = True
            filtered.append(job)
        return filtered
