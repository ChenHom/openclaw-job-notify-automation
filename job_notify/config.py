"""Configuration loading for job notification automation."""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_DIR = Path("~/.config/openclaw-job-notify").expanduser()


@dataclass(frozen=True)
class JobNotifyConfig:
    profile_dir: Path
    firestore_project_id: str = ""
    firestore_database: str = "(default)"
    node_binary: str = "node"
    firebase_tools_auth_module: str = "firebase-tools/lib/auth.js"
    sender_command: tuple[str, ...] = ()
    search_hints_path: Path | None = None
    daily_report_dir: Path | None = None
    weekly_report_dir: Path | None = None

    @property
    def effective_search_hints_path(self) -> Path:
        return self.search_hints_path or self.profile_dir / "search_hints.json"

    @property
    def effective_daily_report_dir(self) -> Path:
        return self.daily_report_dir or self.profile_dir / "reports" / "daily"

    @property
    def effective_weekly_report_dir(self) -> Path:
        return self.weekly_report_dir or self.profile_dir / "reports" / "weekly"


def load_config(*, profile_dir: str | Path | None = None, config_file: str | Path | None = None) -> JobNotifyConfig:
    root = Path(profile_dir or os.getenv("JOB_NOTIFY_PROFILE_DIR") or DEFAULT_PROFILE_DIR).expanduser()
    path = Path(config_file).expanduser() if config_file else root / "config.json"
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))

    def setting(name: str, env: str, default: Any = "") -> Any:
        return os.getenv(env) or data.get(name, default)

    return JobNotifyConfig(
        profile_dir=root,
        firestore_project_id=str(setting("firestoreProjectId", "JOB_NOTIFY_FIRESTORE_PROJECT_ID")),
        firestore_database=str(setting("firestoreDatabase", "JOB_NOTIFY_FIRESTORE_DATABASE", "(default)")),
        node_binary=str(setting("nodeBinary", "JOB_NOTIFY_NODE_BINARY", "node")),
        firebase_tools_auth_module=str(setting("firebaseToolsAuthModule", "JOB_NOTIFY_FIREBASE_TOOLS_AUTH_MODULE", "firebase-tools/lib/auth.js")),
        sender_command=parse_command(setting("senderCommand", "JOB_NOTIFY_SENDER_COMMAND", [])),
        search_hints_path=optional_path(setting("searchHintsPath", "JOB_NOTIFY_SEARCH_HINTS_PATH", None), root),
        daily_report_dir=optional_path(setting("dailyReportDir", "JOB_NOTIFY_DAILY_REPORT_DIR", None), root),
        weekly_report_dir=optional_path(setting("weeklyReportDir", "JOB_NOTIFY_WEEKLY_REPORT_DIR", None), root),
    )


def optional_path(value: Any, root: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else root / path


def parse_command(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return tuple(shlex.split(str(value)))


def add_config_args(parser: Any) -> None:
    parser.add_argument("--profile-dir", help="Private profile directory. Defaults to JOB_NOTIFY_PROFILE_DIR or ~/.config/openclaw-job-notify")
    parser.add_argument("--config", help="JSON config file. Defaults to <profile-dir>/config.json")
