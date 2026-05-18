#!/usr/bin/env python3
"""Weekly 104 job search notifier for Claw Notify."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_notify.config import add_config_args, load_config  # noqa: E402
from job_notify.domain import (  # noqa: E402
    SEARCH_KEYWORDS,
    TAICHUNG_AREAS,
    WEEKLY_CRITERIA,
    Job,
    job_to_feedback_snapshot,
    normalize_104_item,
    weekly_candidate_ok,
)
from job_notify.notify_sender import send_firebase  # noqa: E402
from job_notify.profile_repository import ProfileRepository  # noqa: E402
from job_notify.search_hints import adjusted_relevance, load_profile_search_hints, load_search_hints  # noqa: E402

API_URL = "https://www.104.com.tw/jobs/search/api/jobs"
TAIPEI = timezone(timedelta(hours=8))

def request_json(params: dict[str, object]) -> dict:
    query = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 OpenClaw 104 job notifier",
            "Referer": "https://www.104.com.tw/jobs/search/",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=35) as res:
        return json.loads(res.read().decode("utf-8", "replace"))


def fetch_group(group: str, *, remote: bool, area: str | None, pages_per_keyword: int, now: datetime, search_hints: dict | None = None) -> list[Job]:
    seen: set[str] = set()
    seen_remote_roles: set[tuple[str, str, str]] = set()
    jobs: list[Job] = []
    for keyword in SEARCH_KEYWORDS:
        for page in range(1, pages_per_keyword + 1):
            params: dict[str, object] = {
                "ro": "1",  # full-time
                "keyword": keyword,
                "isnew": "30",
                "order": "11",
                "asc": "0",
                "page": str(page),
                "pagesize": "30",
                "jobsource": "joblist_search",
                "sctp": "M",
                "scmin": "45000",
            }
            if remote:
                params["remoteWork"] = "1"
            if area:
                params["area"] = area
            data = request_json(params)
            items = data.get("data") or []
            if not items:
                break
            for item in items:
                key = str(item.get("jobNo") or (item.get("link") or {}).get("job") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                if not weekly_candidate_ok(item, now=now, remote=remote, area=area):
                    continue
                job = normalize_104_item(item, group=group, keyword=keyword)
                if remote:
                    # Some companies publish one fully-remote role repeatedly under multiple cities.
                    # Keep one card so the weekly list stays useful instead of showing duplicates.
                    role_key = (job.company, job.title, "")
                    if role_key in seen_remote_roles:
                        continue
                    seen_remote_roles.add(role_key)
                jobs.append(job)
            # Be polite to 104.
            time.sleep(0.25)
    hints = search_hints or {}
    jobs.sort(key=lambda job: (-adjusted_relevance(job.relevance, job_to_feedback_snapshot(job, source_context=job.group).get("tags", []), hints), -int(job.appear_date or 0), job.company, job.title))
    return jobs


def job_to_payload(job: Job) -> dict[str, object]:
    updated = ""
    if job.appear_date:
        updated = f"{job.appear_date[4:6]}/{job.appear_date[6:8]}"
    feedback = job_to_feedback_snapshot(job, source_context=job.group)
    return {
        **feedback,
        "company": job.company,
        "title": job.title,
        "description": job.description,
        "salary": job.salary,
        "location": job.location,
        "updated": updated,
        "url": job.url,
        "relevance": job.relevance,
    }


def build_summary(remote_jobs: list[Job], taichung_jobs: list[Job]) -> str:
    return (
        f"本週 104 職缺快篩：完全遠端 {len(remote_jobs)} 筆、台中指定區域 {len(taichung_jobs)} 筆。"
        "點開職缺列表可在自製網頁篩選遠端／台中職缺；"
        f"條件為 {WEEKLY_CRITERIA}"
    )


def build_job_groups(remote_jobs: list[Job], taichung_jobs: list[Job], limit: int | None = None) -> list[dict[str, object]]:
    return [
        {
            "key": "remote",
            "title": "完全遠端",
            "total": len(remote_jobs),
            "shown": len(remote_jobs if limit is None else remote_jobs[:limit]),
            "items": [job_to_payload(job) for job in (remote_jobs if limit is None else remote_jobs[:limit])],
        },
        {
            "key": "local",
            "title": "台中：西屯／北屯／北區／西區",
            "total": len(taichung_jobs),
            "shown": len(taichung_jobs if limit is None else taichung_jobs[:limit]),
            "items": [job_to_payload(job) for job in (taichung_jobs if limit is None else taichung_jobs[:limit])],
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print payload instead of sending")
    parser.add_argument("--limit", type=int, default=None, help="Optional max jobs to store per group")
    parser.add_argument("--pages-per-keyword", type=int, default=4, help="104 API pages to scan per keyword")
    parser.add_argument("--hints-file", help="Optional search hints JSON path. Defaults to configured profile hints path.")
    add_config_args(parser)
    args = parser.parse_args()

    config = load_config(profile_dir=args.profile_dir, config_file=args.config)
    profile_repo = ProfileRepository(config)
    now = datetime.now(TAIPEI)
    search_hints = load_search_hints(args.hints_file) if args.hints_file else load_profile_search_hints(profile_repo)
    remote_jobs = fetch_group("remote", remote=True, area=None, pages_per_keyword=args.pages_per_keyword, now=now, search_hints=search_hints)
    taichung_jobs = fetch_group(
        "taichung",
        remote=False,
        area=",".join(sorted(TAICHUNG_AREAS)),
        pages_per_keyword=args.pages_per_keyword,
        now=now,
        search_hints=search_hints,
    )
    summary = build_summary(remote_jobs, taichung_jobs)
    payload = {
        "type": "jobs_104",
        "source": "104",
        "sourceName": "104 職缺快篩",
        "title": f"104 後端職缺快篩｜遠端 {len(remote_jobs)}／台中 {len(taichung_jobs)}",
        "summary": summary,
        "url": "",
        "publishedAt": now.isoformat(),
        "tags": ["weekly", "jobs", "104", "php", "backend", "taichung", "remote"],
        "notificationFrequency": "weekly",
        "criteria": WEEKLY_CRITERIA,
        "searchHints": search_hints,
        "jobGroups": build_job_groups(remote_jobs, taichung_jobs, args.limit),
    }
    send_firebase(payload, args.dry_run, config=config)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"104 job notify failed: {exc}", file=sys.stderr)
        raise
