from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from job_agent.apply.browser import BrowserApplyAgent
from job_agent.config import load_portals, load_states
from job_agent.models import AgentPolicy, ApplyAction, ApplyOutcome, JobProfile, JobStatus, RankedJob, SearchResult
from job_agent.notifications import EmailNotifier
from job_agent.tracker import MarkdownTracker
from job_agent.ranker import JobRanker
from job_agent.sources import CareerOpsPortalSource, GreenhouseSource, LeverSource, RemoteOKSource, WebSearchSource
from job_agent.storage import JobStore


APPLY_FRIENDLY_PLATFORM_QUERIES = [
    "site:jobs.ashbyhq.com automation engineer OR qa automation OR sdet OR rpa",
    "site:jobs.workable.com automation engineer OR qa automation OR sdet OR rpa",
    "site:jobs.smartrecruiters.com automation engineer OR qa automation OR sdet OR rpa",
    "site:careers.recruitee.com automation engineer OR qa automation OR sdet OR rpa",
    "site:jobs.personio.com automation engineer OR qa automation OR sdet OR rpa",
    "site:bamboohr.com/jobs automation engineer OR qa automation OR sdet OR rpa",
    "site:boards.eu.greenhouse.io automation engineer OR qa automation OR sdet OR rpa",
    "site:apply.workable.com internship automation OR qa automation intern OR sdet intern",
]


def _normalize_job_url(url: str) -> str:
    replacements = {
        "https://www.boards.greenhouse.io/": "https://boards.greenhouse.io/",
        "http://www.boards.greenhouse.io/": "https://boards.greenhouse.io/",
        "https://www.job-boards.greenhouse.io/": "https://job-boards.greenhouse.io/",
        "http://www.job-boards.greenhouse.io/": "https://job-boards.greenhouse.io/",
    }
    normalized = url.strip()
    for old, new in replacements.items():
        if normalized.startswith(old):
            return new + normalized[len(old):]
    return normalized


def _linkedin_queries(request: str, profile: JobProfile) -> list[str]:
    keywords = [
        "automation engineer",
        "qa automation",
        "sdet",
        "rpa",
        "workflow automation",
        "automation internship",
    ]
    location_terms = [term for term in profile.work_preferences.preferred_locations[:3] if term]
    base_location = location_terms[0] if location_terms else "remote"
    queries: list[str] = []
    lowered_request = request.lower()
    for keyword in keywords:
        if keyword in lowered_request or "automation" in lowered_request:
            queries.append(f"site:www.linkedin.com/jobs/view {keyword} {base_location}")
    if not queries:
        queries.append(f"site:www.linkedin.com/jobs/view automation engineer {base_location}")
    return queries


class JobAgentWorkflow:
    def __init__(self, profile: JobProfile, policy: AgentPolicy) -> None:
        self.profile = profile
        self.policy = policy
        self.portals = load_portals(policy.portals_config_path)
        self.states = load_states(policy.states_config_path)
        self.store = JobStore(policy.database_path)
        self.ranker = JobRanker()
        self.apply_agent = BrowserApplyAgent(profile, policy)
        self.notifier = EmailNotifier(policy.notifications, profile)
        self.tracker = MarkdownTracker(policy.tracker_markdown_path, self.states)

    async def search(self, request: str) -> SearchResult:
        sources = []
        web_source = WebSearchSource()
        if self.policy.search.use_career_ops_portals and (
            self.portals.search_queries or self.portals.tracked_companies
        ):
            sources.append(CareerOpsPortalSource(self.portals))
        if self.policy.search.use_greenhouse:
            sources.append(GreenhouseSource())
        if self.policy.search.use_lever:
            sources.append(LeverSource())
        if self.policy.search.use_remoteok:
            sources.append(RemoteOKSource())
        if self.policy.search.use_web_search:
            sources.append(web_source)

        batches = await asyncio.gather(
            *[source.search(request, self.profile, self.policy.max_search_results_per_source) for source in sources],
            return_exceptions=True,
        )
        jobs = []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            jobs.extend(batch)

        if self.policy.search.use_web_search and self.policy.search.use_extra_apply_platforms:
            extra_queries = list(APPLY_FRIENDLY_PLATFORM_QUERIES)
            extra_queries.extend(self.policy.search.extra_platform_queries)
            per_query_limit = max(5, min(25, self.policy.max_search_results_per_source // 2))
            extra_batches = await asyncio.gather(
                *[web_source.search(query, self.profile, per_query_limit) for query in extra_queries],
                return_exceptions=True,
            )
            for batch in extra_batches:
                if isinstance(batch, Exception):
                    continue
                jobs.extend(batch)

        if self.policy.search.use_web_search and self.policy.search.use_linkedin:
            linkedin_queries = _linkedin_queries(request, self.profile)
            linkedin_batches = await asyncio.gather(
                *[web_source.search(query, self.profile, max(5, self.policy.max_search_results_per_source // 3)) for query in linkedin_queries],
                return_exceptions=True,
            )
            for batch in linkedin_batches:
                if isinstance(batch, Exception):
                    continue
                jobs.extend(batch)

        deduped = {job.dedupe_key(): job for job in jobs}
        for job in deduped.values():
            job.url = _normalize_job_url(str(job.url))
        ranked = self.ranker.rank(list(deduped.values()), self.profile, request)
        for item in ranked:
            self.store.upsert_ranked_job(item)
        self.tracker.export(self.store)
        return SearchResult(request=request, jobs=ranked)

    async def apply(self, dedupe_key: str, action: ApplyAction):
        job = self.store.get_job(dedupe_key)
        if job is None:
            raise KeyError(f"Job not found: {dedupe_key}")
        outcome = await self.apply_agent.run(job, action)
        if self.policy.notifications.enabled:
            try:
                notification_result = self.notifier.notify(outcome)
                outcome.notes.append(notification_result)
            except Exception as exc:  # noqa: BLE001
                outcome.notes.append(f"Email notification failed: {exc}")
        self.store.record_apply_outcome(outcome)
        self.tracker.export(self.store)
        return outcome

    async def autopilot(self, request: str, max_jobs: int, apply_limit: int, action: ApplyAction) -> SearchResult:
        result = await self.search(request)
        shortlisted: list[RankedJob] = result.jobs[:max_jobs]
        blocked_domains: set[str] = set()
        if self.policy.skip_domains_with_recent_blockers:
            blocked_domains = self.store.get_recently_blocked_domains(self.policy.blocked_domain_cooldown_hours)

        for ranked in shortlisted[:apply_limit]:
            current_status = self.store.get_job_status(ranked.job.dedupe_key())
            if current_status is not None and current_status != JobStatus.discovered.value:
                continue

            domain = urlparse(str(ranked.job.url)).netloc.lower()
            if domain in blocked_domains:
                skipped_outcome = ApplyOutcome(
                    job=ranked.job,
                    action=action,
                    status=JobStatus.skipped,
                    notes=[
                        f"Skipped due to recent blocker history for domain: {domain}",
                        "Domain cooldown avoids repeated CAPTCHA/OTP blocks.",
                    ],
                    blocker_type="domain_cooldown",
                    blocker_signals=[domain],
                )
                self.store.record_apply_outcome(skipped_outcome)
                continue

            outcome = await self.apply(ranked.job.dedupe_key(), action)
            if outcome.status == JobStatus.blocked and outcome.blocker_type in {"captcha", "otp", "botwall"}:
                blocked_domains.add(domain)
        return SearchResult(request=request, jobs=shortlisted)
