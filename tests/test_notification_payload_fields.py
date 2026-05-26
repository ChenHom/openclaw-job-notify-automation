from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from job_notify.domain import Job


def load_script(name: str):
    module_path = Path(__file__).resolve().parents[1] / "bin" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def example_job() -> Job:
    return Job(
        group="remote",
        company="Example Co",
        title="PHP 後端工程師",
        description="Laravel API",
        salary="月薪 80,000",
        location="台中市",
        appear_date="2026-05-26",
        url="https://www.104.com.tw/job/abc123",
        job_no="abc123",
        relevance=90,
        source_keyword="PHP",
        remote_type=2,
    )


def test_weekly_104_payload_marks_translation_disabled():
    module = load_script("104_job_notify")
    payload = module.build_notification_payload([example_job()], [], {}, limit=1, now=datetime(2026, 5, 26, tzinfo=timezone.utc))

    assert payload["translationEnabled"] is False
    assert payload["language"] == "zh-Hant"


def test_daily_104_payload_marks_translation_disabled():
    module = load_script("daily_high_fit_job_notify")
    daily_job = module.DailyJob(rank=1, company="Example Co", title="PHP 後端工程師", url="https://www.104.com.tw/job/abc123")
    payload = module.build_notification_payload(Path("2026-05-26.md"), "# Report", [daily_job], datetime(2026, 5, 26, tzinfo=timezone.utc))

    assert payload["translationEnabled"] is False
    assert payload["language"] == "zh-Hant"


def test_job_feedback_payload_marks_translation_disabled():
    module = load_script("job_feedback_weekly_report")
    payload = module.build_payload("uid1", "# Report", {}, datetime(2026, 5, 26, tzinfo=timezone.utc))

    assert payload["translationEnabled"] is False
    assert payload["language"] == "zh-Hant"
