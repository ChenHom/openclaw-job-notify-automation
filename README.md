# OpenClaw Job Notify Automation

### 職責說明
本專案為通知自動化引擎，負責執行職務探索、過濾、排序、基於反饋調整個人偏好設定、產生報告以及建立通知內容。
它不負責 Firebase/PWA 收件匣 UI 或生產環境的推送服務，該部分由 `openclaw-notify-inbox` 負責。本引擎僅需透過設定好的發送指令傳遞訊息，允許使用者在不更動領域邏輯的情況下切換其他的收件匣或傳遞系統。運行期間的私密狀態與配置則存放於如 `openclaw-job-notify-profile` 的檔案位置。

## Contents

- `bin/104_job_notify.py`: weekly 104 job search payload sender.
- `bin/daily_high_fit_job_notify.py`: daily high-fit job report payload sender.
- `bin/application_worker.py`: simplified 104 application workflow worker; converts `requested` application requests into private `jd.json` / `source-resume.json` artifacts.
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
bin/application_worker.py --limit 5 --profile-dir /home/hom/services/openclaw-job-notify-profile
bin/application_worker.py --limit 5 --skip-resume --no-fetch-remote-job --profile-dir /tmp/job-notify-demo-profile
bin/application_worker.py --uid smoke_p1_p3 --application-id '104_smoke_p1p3_程式' --no-fetch-remote-job --profile-dir /home/hom/services/openclaw-job-notify-profile
```

## 104 Application Workflow

The simplified Phase 2/3 worker processes `jobApplications/{uid}/requests/{applicationId}` documents with `status: requested`.

Private artifacts are written under:

```text
<profile-dir>/applications/<applicationId>/
  manifest.json
  jd.json
  source-resume.json
```

The worker keeps Firestore public-safe: it updates status fields only and does not write full JD text, resume text, generated package content, contact info, 104 session data, or local artifact paths to Firestore.

Phase 2 can be run alone with `--skip-resume`. Phase 3 calls `/home/hom/services/104-resume-automation` by default and reads its explicit `--result` JSON contract instead of parsing stdout.

For production-safe smoke tests, pass both `--uid` and `--application-id` so the worker reads one exact request document directly instead of scanning collection groups. This avoids composite-index requirements and prevents a smoke run from picking up unrelated real requests.

## Verification

```bash
python3 -m py_compile job_notify/*.py bin/*.py
python3 -m pytest tests -q
```

Production scripts require a private profile config with Firestore and sender settings.
