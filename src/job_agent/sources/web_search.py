from __future__ import annotations

from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from job_agent.models import JobPosting, JobProfile
from job_agent.sources.base import BaseJobSource


class WebSearchSource(BaseJobSource):
    name = "web_search"

    async def search(self, request: str, profile: JobProfile, limit: int) -> list[JobPosting]:
        queries = profile.search.default_queries or [request]
        jobs: list[JobPosting] = []
        for query in queries[:3]:
            jobs.extend(await self.search_query(query, limit=max(1, limit - len(jobs))))
            if len(jobs) >= limit:
                return jobs[:limit]
        return jobs[:limit]

    async def search_query(self, query: str, limit: int, company_hint: str | None = None) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "job-agent/0.1"}) as client:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            response = await client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for index, result in enumerate(soup.select(".result"), start=1):
                anchor = result.select_one(".result__title a")
                snippet = result.select_one(".result__snippet")
                if anchor is None:
                    continue
                raw_url = anchor.get("href", "")
                resolved_url = self._resolve_duckduckgo_url(raw_url)
                company = company_hint or urlparse(resolved_url).netloc or "search-result"
                jobs.append(
                    JobPosting(
                        external_id=f"{query[:25]}-{index}",
                        source=self.name,
                        title=anchor.get_text(" ", strip=True),
                        company=company,
                        url=resolved_url,
                        location="",
                        remote="remote" in (snippet.get_text(" ", strip=True).lower() if snippet else ""),
                        description=snippet.get_text(" ", strip=True) if snippet else "",
                        metadata={"query": query},
                    )
                )
                if len(jobs) >= limit:
                    return jobs
        return jobs[:limit]

    def _resolve_duckduckgo_url(self, raw_url: str) -> str:
        if raw_url.startswith("//"):
            raw_url = f"https:{raw_url}"
        parsed = urlparse(raw_url)
        if "duckduckgo.com" not in parsed.netloc:
            return raw_url
        redirect_target = parse_qs(parsed.query).get("uddg", [])
        if redirect_target:
            return unquote(redirect_target[0])
        return raw_url
