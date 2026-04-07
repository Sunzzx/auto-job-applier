from __future__ import annotations

from pathlib import Path


def resolve_request(request: str | None = None, request_file: str | None = None) -> str:
    if request:
        return request.strip()
    if request_file:
        return Path(request_file).expanduser().read_text(encoding="utf-8").strip()
    raise ValueError("Provide either --request or --request-file.")
