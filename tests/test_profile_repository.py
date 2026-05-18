from __future__ import annotations

from job_notify.config import load_config
from job_notify.profile_repository import ProfileRepository


def test_profile_repository_reads_and_writes_private_files(tmp_path):
    config = load_config(profile_dir=tmp_path)
    repo = ProfileRepository(config)

    assert repo.read_seen_jobs() == {"seen": [], "notes": {}}
    assert repo.read_resume_summary() == ""
    assert repo.first_search_hint() == {"boostTags": [], "downrankTags": [], "boostSkills": []}

    repo.write_seen_jobs({"seen": ["job-a"], "notes": {"job-a": "reviewed"}})
    repo.write_search_hints({"hints": [{"boostTags": ["backend"], "downrankTags": ["go_heavy"], "boostSkills": ["php"]}]})
    repo.resume_summary_path.write_text("Backend resume summary", encoding="utf-8")
    daily = repo.write_daily_report("2026-05-18", "# Daily")
    weekly = repo.write_weekly_report("u1", "2026-W21", "# Weekly")

    assert repo.read_seen_jobs()["seen"] == ["job-a"]
    assert repo.first_search_hint()["boostTags"] == ["backend"]
    assert repo.read_resume_summary() == "Backend resume summary"
    assert daily == tmp_path / "reports" / "daily" / "2026-05-18.md"
    assert weekly == tmp_path / "reports" / "weekly" / "u1-2026-W21.md"
