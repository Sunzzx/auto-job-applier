from __future__ import annotations

import os
from typing import Iterable

from job_agent.models import JobPosting, JobProfile, RankedJob


def _matches_any(text: str, words: Iterable[str]) -> list[str]:
    normalized = text.lower()
    return [word for word in words if word.lower() in normalized]


class JobRanker:
    def rank(self, jobs: list[JobPosting], profile: JobProfile, request: str) -> list[RankedJob]:
        ranked = [self._score_job(job, profile, request) for job in jobs]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    def _score_job(self, job: JobPosting, profile: JobProfile, request: str) -> RankedJob:
        text = " ".join(
            [
                job.title,
                job.company,
                job.location,
                job.description,
                request,
                " ".join(profile.work_preferences.keywords),
            ]
        ).lower()
        score = 0.0
        reasons: list[str] = []

        title_hits = _matches_any(job.title, profile.work_preferences.titles)
        score += 15 * len(title_hits)
        reasons.extend(f"title match: {hit}" for hit in title_hits)

        keyword_hits = _matches_any(text, profile.work_preferences.keywords)
        score += 6 * len(keyword_hits)
        reasons.extend(f"keyword match: {hit}" for hit in keyword_hits[:5])

        seniority_hits = _matches_any(text, profile.work_preferences.target_seniority)
        score += 4 * len(seniority_hits)
        reasons.extend(f"seniority hint: {hit}" for hit in seniority_hits)

        if job.remote:
            score += 12
            reasons.append("remote-friendly")

        if any(loc.lower() in text for loc in profile.work_preferences.preferred_locations):
            score += 8
            reasons.append("preferred location")

        excluded = _matches_any(text, profile.work_preferences.excluded_keywords)
        if excluded:
            score -= 25 * len(excluded)
            reasons.extend(f"excluded keyword: {hit}" for hit in excluded)

        if "visa" in text and not profile.work_preferences.visa_sponsorship_required:
            score += 2
            reasons.append("mentions visa or sponsorship")

        if "salary" in text or job.compensation:
            score += 3
            reasons.append("compensation available")

        if os.getenv("OPENAI_API_KEY"):
            reasons.append("llm-assisted ranking available but deterministic score used by default")

        return RankedJob(job=job, score=score, reasons=reasons[:8])
