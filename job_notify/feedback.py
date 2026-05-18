"""Job feedback scoring and reporting domain helpers."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

STATUS_WEIGHTS = {
    "interested": 1.0,
    "later": 0.5,
    "want_to_apply": 2.0,
    "applied": 3.0,
    "not_fit": -2.0,
    "archived": -1.0,
}

STATUS_LABELS = {
    "interested": "有興趣",
    "later": "之後再看",
    "want_to_apply": "想投",
    "applied": "已投",
    "not_fit": "不適合",
    "archived": "封存",
}

POSITIVE_STATUSES = {"interested", "later", "want_to_apply", "applied"}
NEGATIVE_STATUSES = {"not_fit", "archived"}


@dataclass(frozen=True)
class FeedbackRecord:
    id: str
    uid: str
    job_key: str
    status: str
    reason_tags: tuple[str, ...]
    negative_tags: tuple[str, ...]
    source_contexts: tuple[str, ...]
    snapshot: dict[str, Any]
    updated_at: str

    @property
    def weight(self) -> float:
        return STATUS_WEIGHTS.get(self.status, 0.0)


def normalize_feedback(doc: dict[str, Any]) -> FeedbackRecord:
    return FeedbackRecord(
        id=str(doc.get("id") or doc.get("jobId") or doc.get("jobKey") or ""),
        uid=str(doc.get("uid") or ""),
        job_key=str(doc.get("jobKey") or ""),
        status=str(doc.get("status") or ""),
        reason_tags=tuple(str(tag) for tag in doc.get("reasonTags") or []),
        negative_tags=tuple(str(tag) for tag in doc.get("negativeTags") or []),
        source_contexts=tuple(str(item) for item in doc.get("sourceContexts") or []),
        snapshot=dict(doc.get("snapshot") or {}),
        updated_at=str(doc.get("updatedAt") or doc.get("createdAt") or ""),
    )


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def salary_band(value: str) -> str:
    digits = [int(part) for part in re.findall(r"\d{2,3},?\d{3}|\d+", value.replace(",", ""))]
    if not digits:
        return "unknown"
    low = max(digits) if "以上" in value else min(digits)
    if low >= 80000:
        return "80k_plus"
    if low >= 60000:
        return "60k_80k"
    if low >= 45000:
        return "45k_60k"
    return "below_45k"


def profile_from_feedback(records: list[FeedbackRecord], *, uid: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    scores: dict[str, dict[str, dict[str, float | int]]] = {
        "tags": {},
        "skills": {},
        "locations": {},
        "workModes": {},
        "salaryBands": {},
        "statuses": {},
    }
    buckets: dict[str, Counter] = defaultdict(Counter)
    score_buckets: dict[str, Counter] = defaultdict(Counter)

    for record in records:
        if record.uid != uid:
            continue
        weight = record.weight
        snapshot = record.snapshot
        tags = set(record.reason_tags)
        tags.update(str(tag) for tag in snapshot.get("tags") or [])
        tags.update(record.negative_tags)
        skills = [str(skill) for skill in snapshot.get("skills") or []]
        location = str(snapshot.get("location") or "")
        salary = str(snapshot.get("salary") or "")
        work_modes = []
        if "remote" in tags or "遠端" in location:
            work_modes.append("remote")
        if "台中" in location:
            work_modes.append("taichung")
        for tag in tags:
            buckets["tags"][tag] += 1
            score_buckets["tags"][tag] += weight
        for skill in skills:
            normalized = skill.lower()[:60]
            buckets["skills"][normalized] += 1
            score_buckets["skills"][normalized] += weight
        if location:
            key = "taichung" if "台中" in location else location[:40]
            buckets["locations"][key] += 1
            score_buckets["locations"][key] += weight
        if salary:
            band = salary_band(salary)
            buckets["salaryBands"][band] += 1
            score_buckets["salaryBands"][band] += weight
        for mode in work_modes:
            buckets["workModes"][mode] += 1
            score_buckets["workModes"][mode] += weight
        buckets["statuses"][record.status] += 1
        score_buckets["statuses"][record.status] += weight

    for section, counter in buckets.items():
        scores[section] = {
            key: {"count": int(count), "score": round(float(score_buckets[section][key]), 3)}
            for key, count in sorted(counter.items(), key=lambda item: (-score_buckets[section][item[0]], item[0]))
        }

    return {
        "uid": uid,
        "version": 1,
        "feedbackCount": sum(1 for record in records if record.uid == uid),
        "scores": scores,
        "lastComputedAt": now.isoformat(),
    }


def recent_records(records: list[FeedbackRecord], *, now: datetime, days: int = 7) -> list[FeedbackRecord]:
    cutoff = now - timedelta(days=days)
    result = []
    for record in records:
        updated = parse_time(record.updated_at)
        if updated and updated >= cutoff:
            result.append(record)
    return result


def top_scores(profile: dict[str, Any], section: str, *, positive: bool = True, limit: int = 8) -> list[tuple[str, float, int]]:
    items = []
    for key, value in (profile.get("scores", {}).get(section, {}) or {}).items():
        score = float(value.get("score") or 0)
        count = int(value.get("count") or 0)
        if positive and score <= 0:
            continue
        if not positive and score >= 0:
            continue
        items.append((key, score, count))
    items.sort(key=lambda item: (-item[1], item[0]) if positive else (item[1], item[0]))
    return items[:limit]


def build_search_hints(profile: dict[str, Any]) -> dict[str, Any]:
    positive_tags = [key for key, _score, _count in top_scores(profile, "tags", positive=True, limit=12)]
    negative_tags = [key for key, _score, _count in top_scores(profile, "tags", positive=False, limit=12)]
    positive_skills = [key for key, _score, _count in top_scores(profile, "skills", positive=True, limit=10)]
    return {
        "uid": profile.get("uid", ""),
        "generatedAt": profile.get("lastComputedAt", ""),
        "boostTags": positive_tags,
        "downrankTags": negative_tags,
        "boostSkills": positive_skills,
    }


def markdown_report(uid: str, records: list[FeedbackRecord], profile: dict[str, Any], *, now: datetime | None = None, days: int = 7) -> str:
    now = now or datetime.now(timezone.utc)
    recent = recent_records([record for record in records if record.uid == uid], now=now, days=days)
    status_counts = Counter(record.status for record in recent)
    positive_tags = top_scores(profile, "tags", positive=True, limit=8)
    negative_tags = top_scores(profile, "tags", positive=False, limit=8)
    skills = top_scores(profile, "skills", positive=True, limit=8)
    lines = [
        "# 104 職缺偏好週報",
        "",
        f"- UID: `{uid}`",
        f"- 統計時間: {now.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')}",
        f"- 長期 feedback 筆數: {profile.get('feedbackCount', 0)}",
        f"- 近 {days} 天互動: {len(recent)}",
        "",
        "## 本週狀態",
    ]
    if status_counts:
        lines.extend(f"- {STATUS_LABELS.get(status, status)}: {count}" for status, count in sorted(status_counts.items()))
    else:
        lines.append("- 本週尚無新的職缺狀態回饋。")
    lines.extend(["", "## 長期偏好 Top Tags"])
    lines.extend(format_score_lines(positive_tags, empty="- 尚無正向偏好資料。"))
    lines.extend(["", "## 明顯排斥特徵"])
    lines.extend(format_score_lines(negative_tags, empty="- 尚無負向偏好資料。"))
    lines.extend(["", "## 常見能力 / 關鍵字缺口"])
    if skills:
        lines.extend(f"- {key}: score {score:g} / {count} 次" for key, score, count in skills)
    else:
        lines.append("- 資料不足，暫不判斷能力缺口。")
    lines.extend(["", "## 下週搜尋條件建議"])
    hints = build_search_hints(profile)
    if hints["boostTags"]:
        lines.append(f"- 加權：{', '.join(hints['boostTags'][:8])}")
    if hints["downrankTags"]:
        lines.append(f"- 降權：{', '.join(hints['downrankTags'][:8])}")
    if not hints["boostTags"] and not hints["downrankTags"]:
        lines.append("- 先維持目前搜尋條件，等累積更多回饋再調整。")
    return "\n".join(lines).strip() + "\n"


def format_score_lines(items: list[tuple[str, float, int]], *, empty: str) -> list[str]:
    if not items:
        return [empty]
    return [f"- {key}: score {score:g} / {count} 次" for key, score, count in items]
