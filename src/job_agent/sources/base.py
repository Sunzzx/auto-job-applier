from __future__ import annotations

from abc import ABC, abstractmethod

from job_agent.models import JobPosting, JobProfile


class BaseJobSource(ABC):
    name: str

    @abstractmethod
    async def search(self, request: str, profile: JobProfile, limit: int) -> list[JobPosting]:
        raise NotImplementedError
