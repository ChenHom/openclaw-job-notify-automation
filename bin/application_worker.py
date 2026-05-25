#!/usr/bin/env python3
"""Process simplified 104 application requests into private artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from job_notify.application_workflow import (
    ApplicationArtifactRepository,
    ApplicationWorker,
    BasicJobDetailProvider,
    ResumeExportAdapter,
)
from job_notify.config import add_config_args, load_config
from job_notify.firestore_admin import FirestoreApplicationStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_config_args(parser)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--resume-automation-dir", default="/home/hom/services/104-resume-automation")
    parser.add_argument("--skip-resume", action="store_true", help="Stop after writing jd.json and fetching_resume status.")
    parser.add_argument("--no-fetch-remote-job", action="store_true", help="Use request metadata only for jd.json.")
    args = parser.parse_args()

    config = load_config(profile_dir=args.profile_dir, config_file=args.config)
    artifacts = ApplicationArtifactRepository(config.profile_dir)
    store = FirestoreApplicationStore(config)
    job_provider = BasicJobDetailProvider(fetch_remote=not args.no_fetch_remote_job)
    resume_adapter = None if args.skip_resume else ResumeExportAdapter(Path(args.resume_automation_dir))
    worker = ApplicationWorker(
        store=store,
        artifacts=artifacts,
        job_provider=job_provider,
        resume_adapter=resume_adapter,
    )
    results = worker.run_once(limit=args.limit)
    print(json.dumps({"processed": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
