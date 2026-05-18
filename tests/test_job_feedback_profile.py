from __future__ import annotations

from datetime import datetime, timezone

from job_notify.feedback import build_search_hints, markdown_report, normalize_feedback, profile_from_feedback
from job_notify.search_hints import adjusted_relevance


def record(status, tags, *, uid="u1", title="後端工程師", skills=None, updated="2026-05-18T00:00:00+00:00"):
    return normalize_feedback({
        "id": "r1",
        "uid": uid,
        "jobKey": "104:abc",
        "status": status,
        "reasonTags": tags,
        "negativeTags": ["go_heavy"] if status == "not_fit" else [],
        "sourceContexts": ["daily"],
        "snapshot": {
            "company": "公司",
            "title": title,
            "salary": "月薪 80,000～100,000 元",
            "location": "台中市西屯區",
            "skills": skills or ["API", "Redis"],
            "tags": tags,
        },
        "updatedAt": updated,
    })


def test_profile_scores_status_weights_and_tags():
    records = [
        record("interested", ["api", "backend"]),
        record("applied", ["api", "payment"]),
        record("not_fit", ["game"]),
        record("interested", ["api"], uid="u2"),
    ]
    profile = profile_from_feedback(records, uid="u1", now=datetime(2026, 5, 18, tzinfo=timezone.utc))
    assert profile["feedbackCount"] == 3
    assert profile["scores"]["tags"]["api"]["score"] == 4
    assert profile["scores"]["tags"]["payment"]["score"] == 3
    assert profile["scores"]["tags"]["go_heavy"]["score"] == -2


def test_search_hints_and_markdown_report():
    records = [record("applied", ["api", "backend"]), record("not_fit", ["game"])]
    profile = profile_from_feedback(records, uid="u1", now=datetime(2026, 5, 18, tzinfo=timezone.utc))
    hints = build_search_hints(profile)
    assert "api" in hints["boostTags"]
    assert "game" in hints["downrankTags"]
    report = markdown_report("u1", records, profile, now=datetime(2026, 5, 18, tzinfo=timezone.utc))
    assert "104 職缺偏好週報" in report
    assert "下週搜尋條件建議" in report


def test_adjusted_relevance_applies_boost_and_downrank_tags():
    hints = {"boostTags": ["backend", "high_salary"], "downrankTags": ["go_heavy"]}

    assert adjusted_relevance(80, ["backend", "high_salary"], hints) == 96
    assert adjusted_relevance(80, ["backend", "go_heavy"], hints) == 76
