"""Private profile file repository.

This module is the boundary between the public engine and user-specific data.
The public repo owns the file conventions; the actual files live in a private
profile directory selected by config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_notify.config import JobNotifyConfig


class ProfileRepository:
    def __init__(self, config: JobNotifyConfig):
        self.config = config
        self.root = config.profile_dir

    @property
    def seen_jobs_path(self) -> Path:
        return self.root / "seen_jobs.json"

    @property
    def resume_summary_path(self) -> Path:
        return self.root / "resume-summary.md"

    def read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def read_seen_jobs(self) -> dict[str, Any]:
        return self.read_json(self.seen_jobs_path, {"seen": [], "notes": {}})

    def write_seen_jobs(self, data: dict[str, Any]) -> None:
        self.write_json(self.seen_jobs_path, data)

    def read_search_hints(self) -> dict[str, Any]:
        return self.read_json(self.config.effective_search_hints_path, {"hints": []})

    def first_search_hint(self) -> dict[str, Any]:
        data = self.read_search_hints()
        hints = data.get("hints") or []
        if not hints:
            return {"boostTags": [], "downrankTags": [], "boostSkills": []}
        return hints[0]

    def write_search_hints(self, data: dict[str, Any]) -> None:
        self.write_json(self.config.effective_search_hints_path, data)

    def read_resume_summary(self) -> str:
        if not self.resume_summary_path.exists():
            return ""
        return self.resume_summary_path.read_text(encoding="utf-8")

    def daily_report_path(self, date_slug: str) -> Path:
        return self.config.effective_daily_report_dir / f"{date_slug}.md"

    def weekly_report_path(self, uid: str, report_id: str) -> Path:
        return self.config.effective_weekly_report_dir / f"{uid}-{report_id}.md"

    def write_daily_report(self, date_slug: str, content: str) -> Path:
        path = self.daily_report_path(date_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_weekly_report(self, uid: str, report_id: str, content: str) -> Path:
        path = self.weekly_report_path(uid, report_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
