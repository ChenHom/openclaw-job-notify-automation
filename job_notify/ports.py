"""Small interfaces for external adapters.

The domain helpers stay independent from Firestore, notification delivery, and
private profile storage. Runtime scripts may use concrete adapters, while tests
can use fakes implementing these protocols.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class FeedbackStore(Protocol):
    def list_feedback(self) -> list[dict[str, Any]]:
        ...

    def write_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        ...


class NotificationSender(Protocol):
    def send(self, payload: dict[str, Any]) -> None:
        ...


class ProfileStore(Protocol):
    def read_seen_jobs(self) -> dict[str, Any]:
        ...

    def write_seen_jobs(self, data: dict[str, Any]) -> None:
        ...

    def first_search_hint(self) -> dict[str, Any]:
        ...

    def write_search_hints(self, data: dict[str, Any]) -> None:
        ...

    def read_resume_summary(self) -> str:
        ...

    def daily_report_path(self, date_slug: str) -> Path:
        ...

    def write_weekly_report(self, uid: str, report_id: str, content: str) -> Path:
        ...
