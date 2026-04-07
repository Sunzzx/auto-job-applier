from __future__ import annotations

from pathlib import Path

import yaml

from job_agent.models import AgentPolicy, CareerOpsPortals, JobProfile, TrackerStates


def load_yaml(path: str | Path) -> dict:
    text = Path(path).expanduser().read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def load_profile(path: str | Path) -> JobProfile:
    return JobProfile.model_validate(load_yaml(path))


def load_policy(path: str | Path) -> AgentPolicy:
    return AgentPolicy.model_validate(load_yaml(path))


def load_portals(path: str | Path | None) -> CareerOpsPortals:
    if not path:
        return CareerOpsPortals()
    candidate = Path(path).expanduser()
    if not candidate.exists():
        return CareerOpsPortals()
    return CareerOpsPortals.model_validate(load_yaml(candidate))


def load_states(path: str | Path | None) -> TrackerStates:
    if not path:
        return TrackerStates()
    candidate = Path(path).expanduser()
    if not candidate.exists():
        return TrackerStates()
    return TrackerStates.model_validate(load_yaml(candidate))
