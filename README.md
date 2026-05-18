# OpenClaw Job Notify Automation

104 job search and feedback automation used by OpenClaw Notify.

## Contents

- `bin/104_job_notify.py`: weekly 104 job search payload sender.
- `bin/daily_high_fit_job_notify.py`: daily high-fit job report payload sender.
- `bin/job_feedback_profile.py`: rebuilds long-term preference profiles from Firestore feedback.
- `bin/job_feedback_weekly_report.py`: generates weekly preference reports and search hints.
- `job_notify/`: pure domain rules, Firestore admin adapter, search hint handling, sender adapter.
- `tests/`: focused unit tests for filtering, scoring, feedback profile, and search hints.
- `examples/`: profile config and feedback fixtures for local dry-runs.
- `docs/public-template-refactor-plan.md`: public-template refactor plan.
- `docs/ARCHITECTURE.md`: public engine architecture.
- `docs/CONFIGURATION.md`: private profile configuration.
- `docs/SECURITY.md`: public repo safety notes.
- `docs/PRIVATE_DATA.md`: what belongs outside the public repo.

## Configuration

Runtime-specific data should live outside this repository.

Config loading order:

1. CLI: `--profile-dir /path/to/private-profile`
2. Environment: `JOB_NOTIFY_PROFILE_DIR=/path/to/private-profile`
3. Default: `~/.config/openclaw-job-notify`

The profile directory may contain `config.json`, based on `examples/profile.example.json`.
It can also contain private runtime data:

- `seen_jobs.json`
- `search_hints.json`
- `resume-summary.md`
- `reports/daily/*.md`
- `reports/weekly/*.md`

Useful commands:

```bash
bin/job_feedback_profile.py --feedback-json examples/feedback.fixture.json --dry-run --profile-dir /tmp/job-notify-demo-profile
bin/job_feedback_weekly_report.py --feedback-json examples/feedback.fixture.json --dry-run --profile-dir /tmp/job-notify-demo-profile
bin/104_job_notify.py --dry-run --pages-per-keyword 1 --limit 1 --profile-dir /tmp/job-notify-demo-profile
```

## Verification

```bash
python3 -m py_compile job_notify/*.py bin/*.py
python3 -m pytest tests -q
```

Production scripts require a private profile config with Firestore and sender settings.
