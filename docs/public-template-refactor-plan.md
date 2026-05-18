# Public Template Refactor Plan

## Goal

Convert `openclaw-job-notify-automation` from a private, host-specific automation repo into a public-safe template while keeping private job strategy, resume context, operating history, and production credentials outside the public repository.

## Current Context Checked

- Memory confirms P1-P7 job feedback loop is complete and deployed.
- Current public-candidate repo: this engine repository.
- The Firebase frontend/deploy repository remains production-specific and should stay private.
- The automation repo currently contains reusable scripts and tests, but still has host paths, production adapter defaults, and a private roadmap document.

## Target Architecture

### 1. Public Engine Repository

Repository: `openclaw-job-notify-automation`

Contains:

- 104 search/filtering domain logic.
- Feedback scoring and search hint engine.
- Weekly report generation.
- Adapter interfaces for notification sender, Firestore, profile loading.
- CLI entrypoints using config/env, not host-specific paths.
- Example config files and fake fixture data.
- Public docs: README, ARCHITECTURE, CONFIGURATION, SECURITY.

Does not contain:

- Personal resume text or resume paths.
- Personal job preferences as defaults.
- Seen jobs / real report history.
- Production Firebase project id.
- Production Claw Notify sender path.
- Private roadmap and operational logs.

### 2. Private Profile Source

Suggested local/private repo: `~/services/openclaw-job-notify-profile`

Contains:

- `profile.yaml`: job search preferences, locations, salary policy, tech stack weighting.
- `resume-summary.md`: sanitized/private resume context for daily recommendation writing.
- `seen_jobs.json`: user-specific seen/excluded/applied jobs.
- `search_hints.json`: generated preference hints.
- `firestore.env`: project id and runtime adapter settings.
- `report_templates/`: private report wording templates.
- `reports/`: private daily/weekly job reports.

### 3. Private Knowledge / RAG Layer

Contains development and operating memory, not runtime secrets:

- Why Anonymous Auth is used instead of FCM token as identity.
- Long-term score design and feedback taxonomy decisions.
- Go/Golang exclusion rationale.
- Firebase deploy and smoke-test SOP.
- Private roadmap history and verification results.

Runtime scripts should not depend on RAG. RAG is for agents/developers to recover context quickly during future changes.

## File And Interface Refactor

### New Public Files

- `examples/profile.example.yaml`
- `examples/firestore.env.example`
- `examples/feedback.fixture.json`
- `docs/ARCHITECTURE.md`
- `docs/CONFIGURATION.md`
- `docs/SECURITY.md`
- `docs/PRIVATE_DATA.md`

### New Engine Modules

- `job_notify/config.py`
  - Load config from `--profile`, `JOB_NOTIFY_PROFILE_DIR`, or `~/.config/openclaw-job-notify`.
- `job_notify/profile_repository.py`
  - Read resume summary, seen jobs, search hints, report output paths.
- `job_notify/ports.py`
  - Protocols/interfaces for Firestore, notification sender, clock, profile repository.
- `job_notify/report_repository.py`
  - Write reports without hard-coded workspace paths.

### Scripts To Refactor

- `bin/104_job_notify.py`
  - Add `--profile-dir`, `--config`, `--dry-run`.
  - Remove hard-coded hints path.
- `bin/daily_high_fit_job_notify.py`
  - Add configurable report path and sender command.
- `bin/job_feedback_profile.py`
  - Add configurable Firestore project id and hints output path.
- `bin/job_feedback_weekly_report.py`
  - Add configurable report output dir and sender behavior.

## Development Schedule

### P0 - Preparation And Safety Baseline

Size: S

Tasks:

1. [S] Create refactor branch.
2. [S] Run current tests and record baseline.
3. [S] Run secret scan on current repo.
4. [S] Mark private docs/files to remove from public repo.
5. [S] Decide local private profile path.

Done criteria:

- Baseline tests pass.
- Sensitive/current private files are identified.
- No implementation starts before boundaries are clear.

### P1 - Config Boundary

Size: M

Tasks:

1. [M] Add `job_notify/config.py`.
2. [M] Add `examples/profile.example.yaml`.
3. [S] Support profile load priority:
   - CLI `--profile-dir`
   - `JOB_NOTIFY_PROFILE_DIR`
   - `~/.config/openclaw-job-notify`
4. [M] Move hard-coded paths/project IDs into config object.
5. [S] Add unit tests for config loading.

Done criteria:

- Scripts can run with example config.
- No host-specific absolute path is required by public code.

### P2 - Private Profile Repository

Size: M

Tasks:

1. [M] Add `profile_repository.py`.
2. [S] Read `seen_jobs.json`.
3. [S] Read/write `search_hints.json`.
4. [S] Read `resume-summary.md`.
5. [S] Write reports into configured private output dir.
6. [M] Update daily and weekly scripts to use repository.

Done criteria:

- Private profile folder can drive the same workflow.
- Seen/hints/reports no longer need to live in the public repo.

### P3 - Adapter / Port Cleanup

Size: M

Tasks:

1. [S] Add `ports.py` protocols.
2. [M] Refactor Firestore admin adapter to accept project id/database/node path from config.
3. [M] Refactor notification sender to accept sender command from config.
4. [S] Add fake sender for tests/dry-run.
5. [S] Add fake Firestore fixture path for local tests.

Done criteria:

- Core scoring/filtering is independent from Firebase/Claw Notify.
- Tests can run without production credentials.

### P4 - Public Docs Cleanup

Size: M

Tasks:

1. [M] Replace private roadmap with public `docs/ARCHITECTURE.md`.
2. [M] Add `docs/CONFIGURATION.md`.
3. [S] Add `docs/SECURITY.md`.
4. [S] Add `docs/PRIVATE_DATA.md`.
5. [S] Update README for public template usage.
6. [S] Move private roadmap to private profile repo or workspace/RAG notes.

Done criteria:

- Public docs teach setup without exposing private operations.
- Private history is preserved outside the public repo.

### P5 - Private Profile Project

Size: M

Tasks:

1. [S] Create `~/services/openclaw-job-notify-profile`.
2. [M] Move current private report/history inputs there:
   - resume summary reference
   - seen jobs
   - generated hints
   - private report output folder
3. [S] Add strict `.gitignore` for generated/secret files.
4. [S] Optional: initialize private GitHub repo if needed.
5. [S] Add local README explaining what each private file does.

Done criteria:

- Production cron can run from public engine + private profile folder.
- Private profile can be backed up privately without entering public repo.

### P6 - RAG / Memory Separation

Size: M

Tasks:

1. [M] Convert private roadmap into a concise internal architecture note.
2. [M] Store operating decisions in RAG/knowledge:
   - identity/auth design
   - scoring design
   - feedback taxonomy
   - deploy SOP
   - smoke-test checklist
3. [S] Update workspace memory with repo split and profile path.
4. [S] Add a retrieval checklist for future agents/development.

Done criteria:

- Future development can recover context from memory/RAG.
- Runtime still uses explicit files/env, not RAG.

### P7 - Cron Migration And Production Verification

Size: L

Tasks:

1. [M] Update OpenClaw cron prompts/commands to use:
   - public engine path
   - private profile path
2. [M] Run weekly dry-run with private profile.
3. [M] Run daily report dry-run with private profile.
4. [S] Verify no duplicate or missing notifications.
5. [S] Verify weekly search hints still affect ranking.
6. [S] Verify no public repo file is required from private workspace.

Done criteria:

- Existing daily/weekly production behavior remains unchanged.
- Public repo is publishable.
- Private data source drives production behavior.

### P8 - Public Release Hardening

Size: M

Tasks:

1. [S] Run secret scan on full Git history.
2. [S] Run clean clone test.
3. [S] Run tests in clean clone with example fixtures.
4. [S] Mark repo public only after clean scan.
5. [S] Add release tag.

Done criteria:

- Repo can be public without private data, keys, or host-specific assumptions.
- A new user can configure their own private profile and run fixtures.

## Task Size Legend

- S: 15-45 minutes.
- M: 0.5-1.5 days.
- L: 1.5-3 days.

## Recommended Implementation Order

1. P0-P1 first. This removes the biggest public/private boundary risk.
2. P2-P3 next. This makes runtime clean and testable.
3. P4-P6 after the engine boundary is stable.
4. P7 only after private profile path is real.
5. P8 only when ready to make the repo public.

## Risks

- Mixing RAG with runtime config would make runs hard to reproduce. Keep RAG as development memory only.
- Moving paths before tests exist can silently break cron. Keep dry-run checks after each phase.
- Public docs can leak private strategy even without keys. Rewrite docs as generic architecture, not historical notes.
- Existing production scripts still depend on host paths. Migrate cron only after public engine + private profile dry-runs pass.

## Pre-Development Checklist Completed

- Memory search reviewed current decisions and deployed state.
- `workflow-system-designer` guidance reviewed.
- Current repo file layout checked.
- Current split decision: `openclaw-notify-inbox` stays private; `openclaw-job-notify-automation` becomes public template after refactor.

## 2026-05-18 P0-P1 Implementation Notes

### P0 Completed

- Baseline `py_compile` passed.
- Baseline `pytest` passed: 8 tests before refactor.
- Sensitive/path scan identified hard-coded host/runtime values in code:
  - host node binary path
  - production Firebase project id
  - production sender path
  - workspace search hints/report paths
- No production cron was changed.

### P1 Completed

- Added `job_notify.config` with profile-dir based config loading.
- Added CLI config options to scripts:
  - `--profile-dir`
  - `--config`
- Added config source priority:
  - CLI profile dir
  - `JOB_NOTIFY_PROFILE_DIR`
  - `~/.config/openclaw-job-notify`
- Moved hard-coded runtime values behind config:
  - Firestore project id/database
  - Node binary
  - Firebase tools auth module
  - sender command
  - search hints path
  - daily/weekly report directories
- Added `examples/profile.example.json`.
- Added `examples/feedback.fixture.json`.
- Added config unit tests.

### P1 Verification

- `python3 -m py_compile job_notify/*.py bin/*.py`: passed.
- `python3 -m pytest tests -q`: 10 passed.
- `job_feedback_profile.py --feedback-json examples/feedback.fixture.json --dry-run --profile-dir /tmp/job-notify-demo-profile`: passed.
- `job_feedback_weekly_report.py --feedback-json examples/feedback.fixture.json --dry-run --profile-dir /tmp/job-notify-demo-profile`: passed.
- `104_job_notify.py --dry-run --pages-per-keyword 1 --limit 1 --profile-dir /tmp/job-notify-demo-profile`: passed.

### Remaining After P1

- Private roadmap docs still contain host/project references and must be rewritten or moved in P4 before making the repo public.
- Production cron still uses the workspace scripts; migration is intentionally delayed until P7.

## 2026-05-18 P2 Implementation Notes

### P2 Completed

- Added `job_notify.profile_repository.ProfileRepository` as the private profile file boundary.
- Added support for private profile files:
  - `seen_jobs.json`
  - `search_hints.json`
  - `resume-summary.md`
  - `reports/daily/*.md`
  - `reports/weekly/*.md`
- Updated scripts to use the repository:
  - weekly 104 search loads hints through `ProfileRepository`
  - daily sender resolves date slugs through private daily reports
  - profile rebuild writes hints through `ProfileRepository`
  - weekly report writes report/hints through `ProfileRepository`
- Added safe local write modes:
  - `job_feedback_profile.py --no-firestore`
  - `job_feedback_weekly_report.py --no-firestore`
- Added examples:
  - `examples/seen_jobs.example.json`
  - `examples/resume-summary.example.md`
- Added repository tests.

### P2 Verification

- `python3 -m py_compile job_notify/*.py bin/*.py`: passed.
- `python3 -m pytest tests -q`: 11 passed.
- `job_feedback_profile.py --feedback-json examples/feedback.fixture.json --profile-dir <tmp> --write-hints --no-firestore`: wrote private `search_hints.json`.
- `job_feedback_weekly_report.py --feedback-json examples/feedback.fixture.json --profile-dir <tmp> --write-report --write-hints --no-send --no-firestore`: wrote private weekly report and hints.
- `daily_high_fit_job_notify.py --profile-dir <tmp> --dry-run 2026-05-18`: resolved private daily report by date slug and produced 3 structured jobs.
- `104_job_notify.py --dry-run --pages-per-keyword 1 --limit 1 --profile-dir <tmp>`: loaded private `search_hints.json` into payload.

### Remaining After P2

- Private roadmap docs still need to move/rewrite in P4.
- Production cron still uses workspace scripts until P7.
- Adapter boundaries can be further formalized with ports in P3.

## 2026-05-18 P3-P5 Implementation Notes

### P3 Completed

- Added `job_notify.ports` protocols for feedback stores, notification senders, and profile stores.
- Added Firestore adapter classes:
  - `FirestoreFeedbackStore`
  - `FixtureFeedbackStore`
- Added notification sender classes:
  - `CommandNotificationSender`
  - `PrintNotificationSender`
  - `RecordingNotificationSender`
- Added adapter tests.

### P4 Completed

- Added public docs:
  - `docs/ARCHITECTURE.md`
  - `docs/CONFIGURATION.md`
  - `docs/SECURITY.md`
  - `docs/PRIVATE_DATA.md`
- Updated README to point at public docs.
- Removed private implementation roadmap from the public engine repo.
- Copied private roadmap to the private profile project under `private-roadmap/`.

### P5 Completed

- Created private profile project outside the public engine repository.
- Added private profile files:
  - `config.json`
  - `seen_jobs.json`
  - `resume-summary.md`
  - `reports/daily/*.md`
  - optional `search_hints.json`
  - `private-roadmap/104-job-feedback-preference-roadmap.md`
- Added strict `.gitignore` and README.

### Remaining After P5

- Production cron still uses workspace scripts until P7 migration.
- RAG/memory separation is planned for P6.
- Public release hardening remains P8.

## 2026-05-18 P6 Implementation Notes

### P6 Completed

- Converted private roadmap context into a concise internal architecture note.
- Stored the note in the private profile project:
  - `private-roadmap/internal-architecture-note.md`
- Mirrored the note into workspace project memory:
  - `memory/projects/openclaw-job-notify-automation.md`
- Clarified retrieval workflow for future agents:
  - read internal note
  - read public engine docs
  - read private profile README
  - inspect current cron
  - run dry-runs before production changes

### P6 Boundary

- Runtime scripts still use explicit private profile files/env.
- RAG/memory is for development recovery and SOP recall only.

## 2026-05-18 P7 Implementation Notes

### P7 Completed

- Migrated the weekly 104 system crontab from the old workspace script to the public engine:
  - engine: repository checkout path
  - private profile: external private profile path
  - log: private profile log path
- Updated OpenClaw daily high-fit job cron to use the public engine plus private profile.
- Updated OpenClaw weekly feedback cron to write reports and search hints into the private profile.
- Generated private `search_hints.json` from current feedback data.
- Verified weekly 104 dry-run loads private search hints:
  - boost tags: `php`, `ci_cd`
  - downrank tags include `go_heavy`
- Verified daily dry-run can read private daily report data.

### P7 Verification

- `python3 -m py_compile job_notify/*.py bin/*.py`: passed.
- `python3 -m pytest tests -q`: 13 passed.
- `job_feedback_weekly_report.py --profile-dir <private-profile> --write-hints --write-report --no-send --no-firestore`: passed.
- `daily_high_fit_job_notify.py --profile-dir <private-profile> --dry-run 2026-05-18`: passed.
- `104_job_notify.py --dry-run --pages-per-keyword 1 --limit 1 --profile-dir <private-profile>`: passed.

### P7 Follow-Up Gap

- Current long-term feedback scoring downranks broad structural tags like `backend`, `taichung`, and `remote` when many jobs are marked `not_fit`.
- This is too coarse for future recommendation quality: negative weighting should favor explicit reason tags and highly specific job traits over broad search dimensions.
- Suggested next refinement: protect baseline search dimensions from automatic downranking unless the user explicitly marks them as disliked.

## 2026-05-18 P8 Implementation Notes

### P8 Completed

- Rebuilt public Git history as a single sanitized root commit.
- Removed private roadmap history and old host-specific implementation history from the publishable branch.
- Verified the current public tree has no private profile files, production Firebase project id, absolute host paths, or generated runtime reports.
- Clean clone test passed with the sanitized public history.

### P8 Verification Commands

- `python3 -m py_compile job_notify/*.py bin/*.py`: passed.
- `python3 -m pytest tests -q`: passed.
- `git grep` history scan on the sanitized branch: no private host/project hits.
- Clean clone scan and tests: passed.

### Post-P8 Strengthening Backlog

- Add a fixture-level regression test for protecting broad baseline tags from automatic negative scoring.
- Add a public example showing how to keep one private profile per user.
- Add a cron smoke-test checklist that validates the exact production command after each migration.
