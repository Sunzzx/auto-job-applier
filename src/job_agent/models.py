from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    discovered = "discovered"
    shortlisted = "shortlisted"
    previewed = "previewed"
    filled = "filled"
    submitted = "submitted"
    blocked = "blocked"
    skipped = "skipped"


class ApplyAction(str, Enum):
    preview = "preview"
    fill = "fill"
    submit = "submit"


class SalaryPreference(BaseModel):
    currency: str = "INR"
    amount: int = 0


class IdentityProfile(BaseModel):
    full_name: str
    email: str
    phone: str
    location: str
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    website: str | None = None


class WorkPreferences(BaseModel):
    titles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_only: bool = False
    visa_sponsorship_required: bool = False
    minimum_salary: SalaryPreference = Field(default_factory=SalaryPreference)
    excluded_keywords: list[str] = Field(default_factory=list)
    target_seniority: list[str] = Field(default_factory=list)


class Materials(BaseModel):
    resume_path: str
    cover_letter_path: str | None = None
    additional_files: list[str] = Field(default_factory=list)


class EmploymentProfile(BaseModel):
    years_of_experience: int = 0
    current_title: str = ""
    skills: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    work_authorization: dict[str, bool] = Field(default_factory=dict)


class EducationProfile(BaseModel):
    degree: str = ""
    field: str = ""
    institution: str = ""
    graduation_year: int | None = None


class TargetCompanies(BaseModel):
    greenhouse_boards: list[str] = Field(default_factory=list)
    lever_companies: list[str] = Field(default_factory=list)


class SearchProfile(BaseModel):
    default_queries: list[str] = Field(default_factory=list)


class JobProfile(BaseModel):
    identity: IdentityProfile
    work_preferences: WorkPreferences
    materials: Materials
    employment: EmploymentProfile
    education: EducationProfile
    answers: dict[str, str] = Field(default_factory=dict)
    target_companies: TargetCompanies = Field(default_factory=TargetCompanies)
    search: SearchProfile = Field(default_factory=SearchProfile)

    def known_field_values(self) -> dict[str, str]:
        identity_map = self.identity.model_dump(exclude_none=True)
        derived = {
            "full_name": self.identity.full_name,
            "name": self.identity.full_name,
            "email": self.identity.email,
            "phone": self.identity.phone,
            "location": self.identity.location,
            "linkedin": self.identity.linkedin or "",
            "github": self.identity.github or "",
            "portfolio": self.identity.portfolio or self.identity.website or "",
            "website": self.identity.website or self.identity.portfolio or "",
            "current_title": self.employment.current_title,
            "years_of_experience": str(self.employment.years_of_experience),
            "degree": self.education.degree,
            "field": self.education.field,
            "institution": self.education.institution,
        }
        return {**identity_map, **derived, **self.answers}

    def resume_file(self) -> Path:
        return Path(self.materials.resume_path).expanduser()


class SearchFlags(BaseModel):
    use_career_ops_portals: bool = True
    use_greenhouse: bool = True
    use_lever: bool = True
    use_remoteok: bool = True
    use_web_search: bool = True
    use_extra_apply_platforms: bool = True
    extra_platform_queries: list[str] = Field(default_factory=list)
    use_linkedin: bool = True


class EmailNotificationSettings(BaseModel):
    enabled: bool = False
    backend: str = "mail_app"
    recipient: str | None = None
    sender: str | None = None
    subject_prefix: str = "[Job Agent]"
    include_notes: bool = True
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_password_env: str | None = None
    use_tls: bool = True
    use_ssl: bool = False
    timeout_seconds: int = 30


class AgentPolicy(BaseModel):
    database_path: str = ".job-agent/job_agent.db"
    artifacts_dir: str = ".job-agent/artifacts"
    tracker_markdown_path: str = ".job-agent/applications.md"
    portals_config_path: str | None = "examples/portals.example.yaml"
    states_config_path: str | None = "templates/states.yml"
    submit_mode: str = "guarded"
    max_search_results_per_source: int = 40
    max_apply_per_run: int = 5
    allow_domains_for_submit: list[str] = Field(default_factory=list)
    deny_domains: list[str] = Field(default_factory=list)
    stop_on_missing_answers: bool = True
    headless_browser: bool = False
    auto_upload_resume: bool = True
    skip_domains_with_recent_blockers: bool = True
    blocked_domain_cooldown_hours: int = 72
    linkedin_storage_state_path: str = ".job-agent/linkedin-storage.json"
    search: SearchFlags = Field(default_factory=SearchFlags)
    notifications: EmailNotificationSettings = Field(default_factory=EmailNotificationSettings)


class JobPosting(BaseModel):
    external_id: str
    source: str
    title: str
    company: str
    url: HttpUrl | str
    location: str = ""
    remote: bool = False
    description: str = ""
    compensation: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def dedupe_key(self) -> str:
        return f"{self.source}:{self.external_id}"


class RankedJob(BaseModel):
    job: JobPosting
    score: float
    reasons: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    request: str
    generated_at: str = Field(default_factory=utc_now)
    jobs: list[RankedJob] = Field(default_factory=list)


class PortalTitleFilter(BaseModel):
    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)
    seniority_boost: list[str] = Field(default_factory=list)


class PortalSearchQuery(BaseModel):
    name: str
    query: str
    enabled: bool = True


class TrackedCompany(BaseModel):
    name: str
    careers_url: str
    api: str | None = None
    enabled: bool = True
    scan_method: str | None = None
    scan_query: str | None = None
    notes: str | None = None


class CareerOpsPortals(BaseModel):
    title_filter: PortalTitleFilter = Field(default_factory=PortalTitleFilter)
    search_queries: list[PortalSearchQuery] = Field(default_factory=list)
    tracked_companies: list[TrackedCompany] = Field(default_factory=list)


class CanonicalState(BaseModel):
    id: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    dashboard_group: str = ""


class TrackerStates(BaseModel):
    states: list[CanonicalState] = Field(default_factory=list)


@dataclass
class ApplyOutcome:
    job: JobPosting
    action: ApplyAction
    status: JobStatus
    notes: list[str] = field(default_factory=list)
    screenshot_paths: list[str] = field(default_factory=list)
    submitted_at: str | None = None
    blocker_type: str | None = None
    blocker_signals: list[str] = field(default_factory=list)
