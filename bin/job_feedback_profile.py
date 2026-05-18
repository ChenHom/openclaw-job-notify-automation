#!/usr/bin/env python3
"""Rebuild long-term job preference profiles from job feedback."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_notify.config import add_config_args, load_config  # noqa: E402
from job_notify.feedback import build_search_hints, normalize_feedback, profile_from_feedback  # noqa: E402
from job_notify.firestore_admin import list_feedback, write_document  # noqa: E402
from job_notify.profile_repository import ProfileRepository  # noqa: E402


def load_feedback(path: str | None, config) -> list[dict]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return list_feedback(config=config)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback-json", help="Fixture feedback JSON for dry-run/testing")
    parser.add_argument("--uid", help="Limit to one UID")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-firestore", action="store_true", help="Do not write profile documents to Firestore")
    parser.add_argument("--write-hints", action="store_true", help="Write search hints file")
    add_config_args(parser)
    args = parser.parse_args()

    config = load_config(profile_dir=args.profile_dir, config_file=args.config)
    profile_repo = ProfileRepository(config)
    raw = load_feedback(args.feedback_json, config)
    records = [normalize_feedback(item) for item in raw]
    uids = sorted({record.uid for record in records if record.uid})
    if args.uid:
        uids = [uid for uid in uids if uid == args.uid]

    now = datetime.now(timezone.utc)
    profiles = [profile_from_feedback(records, uid=uid, now=now) for uid in uids]
    hints = [build_search_hints(profile) for profile in profiles]

    if not args.dry_run and not args.no_firestore:
        for profile in profiles:
            write_document("jobPreferenceProfiles", str(profile["uid"]), profile, config=config)

    if args.write_hints:
        profile_repo.write_search_hints({"updatedAt": now.isoformat(), "hints": hints})

    if args.dry_run:
        print(json.dumps({"profiles": profiles, "hints": hints}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"ok": True, "profileCount": len(profiles), "hintCount": len(hints), "firestoreWritten": not args.no_firestore}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
