"""Search hint loading and score adjustment for job notifications."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_notify.profile_repository import ProfileRepository


def load_search_hints(path: str | Path | None = None) -> dict[str, Any]:
    if not path:
        return {"boostTags": [], "downrankTags": [], "boostSkills": []}
    target = Path(path)
    if not target.exists():
        return {"boostTags": [], "downrankTags": [], "boostSkills": []}
    data = json.loads(target.read_text(encoding="utf-8"))
    hints = data.get("hints") or []
    if not hints:
        return {"boostTags": [], "downrankTags": [], "boostSkills": []}
    return hints[0]


def load_profile_search_hints(repository: ProfileRepository) -> dict[str, Any]:
    return repository.first_search_hint()


def adjusted_relevance(base_score: int, tags: list[str], hints: dict[str, Any]) -> int:
    boost = set(hints.get("boostTags") or [])
    downrank = set(hints.get("downrankTags") or [])
    tag_set = set(tags or [])
    score = base_score
    score += 8 * len(tag_set & boost)
    score -= 12 * len(tag_set & downrank)
    return score
