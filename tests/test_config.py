from __future__ import annotations

import json

from job_notify.config import load_config


def test_load_config_from_profile_dir(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({
        "firestoreProjectId": "demo-project",
        "senderCommand": ["node", "sender.js"],
        "searchHintsPath": "state/hints.json",
        "dailyReportDir": "reports/daily",
    }), encoding="utf-8")

    config = load_config(profile_dir=tmp_path)

    assert config.firestore_project_id == "demo-project"
    assert config.sender_command == ("node", "sender.js")
    assert config.effective_search_hints_path == tmp_path / "state/hints.json"
    assert config.effective_daily_report_dir == tmp_path / "reports/daily"
    assert config.effective_weekly_report_dir == tmp_path / "reports/weekly"


def test_sender_command_env_string_is_split(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_NOTIFY_SENDER_COMMAND", "node /tmp/sender.js")

    config = load_config(profile_dir=tmp_path)

    assert config.sender_command == ("node", "/tmp/sender.js")
