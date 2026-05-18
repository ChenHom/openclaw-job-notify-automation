# Configuration

Runtime data belongs outside this repository.

## Profile Directory

Config loading order:

1. `--profile-dir /path/to/profile`
2. `JOB_NOTIFY_PROFILE_DIR=/path/to/profile`
3. `~/.config/openclaw-job-notify`

The profile directory may contain:

- `config.json`
- `seen_jobs.json`
- `search_hints.json`
- `resume-summary.md`
- `reports/daily/*.md`
- `reports/weekly/*.md`

## config.json

See `examples/profile.example.json`.

Common fields:

- `firestoreProjectId`
- `firestoreDatabase`
- `nodeBinary`
- `firebaseToolsAuthModule`
- `senderCommand`
- `searchHintsPath`
- `dailyReportDir`
- `weeklyReportDir`

Relative paths are resolved from the profile directory.

## Dry Runs

Use fixture feedback:

```bash
bin/job_feedback_profile.py --feedback-json examples/feedback.fixture.json --dry-run --profile-dir /tmp/job-profile
bin/job_feedback_weekly_report.py --feedback-json examples/feedback.fixture.json --dry-run --profile-dir /tmp/job-profile
```

Use private profile reports:

```bash
bin/daily_high_fit_job_notify.py --profile-dir /path/to/profile --dry-run 2026-05-18
```

