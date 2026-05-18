#!/usr/bin/env python3
"""Build and optionally send weekly job preference reports."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_notify.config import add_config_args, load_config  # noqa: E402
from job_notify.feedback import build_search_hints, markdown_report, normalize_feedback, profile_from_feedback  # noqa: E402
from job_notify.firestore_admin import list_feedback, write_document  # noqa: E402
from job_notify.notify_sender import send_firebase  # noqa: E402
from job_notify.profile_repository import ProfileRepository  # noqa: E402


def load_feedback(path: str | None, config) -> list[dict]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return list_feedback(config=config)


def report_id(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def build_payload(uid: str, report: str, profile: dict, now: datetime) -> dict:
    positive = build_search_hints(profile).get("boostTags", [])[:5]
    summary = "本週尚無職缺偏好回饋。" if not profile.get("feedbackCount") else f"本週職缺偏好分析已更新；目前偏好：{', '.join(positive) if positive else '資料累積中'}。"
    rid = report_id(now)
    return {
        "id": f"job-feedback-weekly-{uid}-{rid}",
        "type": "jobs_preference_weekly",
        "source": "job_feedback",
        "sourceName": "104職缺偏好週報",
        "title": f"104職缺偏好週報｜{rid}",
        "summary": summary,
        "url": "",
        "publishedAt": now.isoformat(),
        "tags": ["weekly", "jobs", "feedback"],
        "notificationFrequency": "weekly",
        "contentMarkdown": report,
        "profile": profile,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback-json", help="Fixture feedback JSON for dry-run/testing")
    parser.add_argument("--uid", help="Limit to one UID")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-send", action="store_true")
    parser.add_argument("--no-firestore", action="store_true", help="Do not write profile/report documents to Firestore")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--write-hints", action="store_true")
    add_config_args(parser)
    args = parser.parse_args()

    config = load_config(profile_dir=args.profile_dir, config_file=args.config)
    profile_repo = ProfileRepository(config)
    now = datetime.now(timezone.utc)
    raw = load_feedback(args.feedback_json, config)
    records = [normalize_feedback(item) for item in raw]
    uids = sorted({record.uid for record in records if record.uid})
    if args.uid:
        uids = [uid for uid in uids if uid == args.uid]

    outputs = []
    hints = []
    for uid in uids:
        profile = profile_from_feedback(records, uid=uid, now=now)
        report = markdown_report(uid, records, profile, now=now)
        payload = build_payload(uid, report, profile, now)
        outputs.append({"uid": uid, "profile": profile, "report": report, "payload": payload})
        hints.append(build_search_hints(profile))
        if not args.dry_run and not args.no_firestore:
            write_document("jobPreferenceProfiles", uid, profile, config=config)
            write_document("jobPreferenceReports", f"{uid}-{report_id(now)}", {"uid": uid, "report": report, "profile": profile, "createdAt": now.isoformat()}, config=config)
        if not args.dry_run:
            if args.write_report:
                profile_repo.write_weekly_report(uid, report_id(now), report)
            if not args.no_send and profile.get("feedbackCount", 0):
                send_firebase(payload, dry_run=False, config=config)

    if args.write_hints and not args.dry_run:
        profile_repo.write_search_hints({"updatedAt": now.isoformat(), "hints": hints})

    if args.dry_run or args.no_send:
        print(json.dumps({"outputs": outputs, "hints": hints}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"ok": True, "reportCount": len(outputs), "sentEligibleCount": sum(1 for item in outputs if item["profile"].get("feedbackCount", 0)), "firestoreWritten": not args.no_firestore}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
