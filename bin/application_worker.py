#!/usr/bin/env python3
"""Process simplified 104 application requests into private artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_notify.application_workflow import (
    ApplicationArtifactRepository,
    ApplicationPackageWorker,
    ApplicationWorker,
    BasicJobDetailProvider,
    ConservativePackageGenerator,
    JdAwarePackageGenerator,
    ResumeExportAdapter,
)
from job_notify.config import add_config_args, load_config
from job_notify.firestore_admin import FirestoreApplicationStore, FixtureApplicationStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_config_args(parser)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--resume-automation-dir", default="/home/hom/services/104-resume-automation")
    parser.add_argument("--application-id", default="", help="Process only one applicationId. Useful for smoke tests.")
    parser.add_argument("--uid", default="", help="Read a specific user's application request directly. Use with --application-id.")
    parser.add_argument("--fixture-request-json", help="Read one request JSON from disk instead of Firestore.")
    parser.add_argument("--generate-package", action="store_true", help="Process generating_package requests into private package artifacts.")
    parser.add_argument("--package-generator", choices=["conservative", "jd-aware"], default="jd-aware")
    parser.add_argument("--skip-resume", action="store_true", help="Stop after writing jd.json and fetching_resume status.")
    parser.add_argument("--no-fetch-remote-job", action="store_true", help="Use request metadata only for jd.json.")
    args = parser.parse_args()

    config = load_config(profile_dir=args.profile_dir, config_file=args.config)
    artifacts = ApplicationArtifactRepository(config.profile_dir)
    if args.fixture_request_json:
        request = json.loads(Path(args.fixture_request_json).read_text(encoding="utf-8"))
        store = FixtureApplicationStore([request])
    else:
        store = FirestoreApplicationStore(config, application_id=args.application_id, uid=args.uid)
    if args.generate_package:
        generator = ConservativePackageGenerator() if args.package_generator == "conservative" else JdAwarePackageGenerator()
        worker = ApplicationPackageWorker(
            store=store,
            artifacts=artifacts,
            generator=generator,
        )
        results = worker.run_once(limit=args.limit)
        print(json.dumps({"processed": len(results), "results": results}, ensure_ascii=False, indent=2))
        return 0

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
