# 104 Application Workflow Development Plan

Date: 2026-05-21

This document turns `docs/104-application-workflow-mvp.md` into an implementation plan.

## Operating Rules

- Use TDD for every phase: write failing tests first, then implement.
- Keep public and private boundaries separate:
  - Public notification shell: `/home/hom/services/openclaw-notify-inbox`
  - Job automation engine: `/home/hom/services/openclaw-job-notify-automation`
  - Private profile/artifacts: `/home/hom/services/openclaw-job-notify-profile`
  - 104 browser automation: `/home/hom/services/104-resume-automation`
- Do not put full resume text, contact info, 104 session data, local file paths, or package contents into Firestore public documents.
- The hosted Firebase UI is not allowed to fetch localhost directly as the primary path.
- Private package content is viewed through a tailnet/local private endpoint.
- MVP does not automatically modify 104 and does not submit applications.

## Phase 0 - Done: Read-Only 104 Resume Export

Owner repo: `/home/hom/services/104-resume-automation`

Current status:

- `npm run resume:export -- --name 程式 --no-raw-text` works.
- It exports `skillsSummary`, `workSkills`, and `autobiography`.
- `.env`, `auth/`, `outputs/`, `screenshots/`, and `node_modules/` are gitignored.
- Root commit: `b86a5cd Initialize 104 resume automation repo`.

Remaining hardening:

- Add an explicit test for login/OTP/captcha detection that maps to `blocked_resume_fetch_auth_required`.
- Add a machine-readable exit/error contract for automation callers.

Done criteria:

- `npm run test` passes.
- `npx tsc --noEmit` passes.
- Auth-expired fixture produces a blocked auth result, not an unstructured exception.

## Phase 1 - Application Request Model

Owner repos:

- `/home/hom/services/openclaw-notify-inbox`
- `/home/hom/services/openclaw-job-notify-automation`

Current implementation status:

- 2026-05-25 simplified Phase 1 is implemented in `/home/hom/services/openclaw-notify-inbox`.
- The hosted UI now adds an `應徵` button to weekly 104 job cards and daily 104 job cards.
- Clicking `應徵` writes a minimal public-safe request to `jobApplications/{uid}/requests/{applicationId}`.
- The simplified `applicationId` is stable per 104 job and resume: `104_<jobId>_程式`; if no job id exists, it falls back to a canonical URL hash.
- Repeated clicks merge into the same request document and update the request instead of creating multiple active attempts.
- Firestore rules now allow only the simplified public-safe field allowlist.
- Full attempt lifecycle, 60-day reopen policy, JD-hash based new attempts, and automation-side worker processing are intentionally deferred to Phase 2+.

Goal:

When the user presses `應徵` on a 104 high-fit job, create or reuse an application attempt without generating private content yet.

Data model:

```text
jobApplications/{uid}/requests/{applicationId}
```

Public-safe fields:

- `applicationId`
- `status`
- `jobUrl`
- `resumeName: "程式"`
- `sourceNotificationId`
- `title`
- `company`
- `jobId`
- `source`
- `uid`
- `createdAt`
- `updatedAt`

Deferred fields:

- `jobIdentityKey`
- `attemptKey`
- `canonicalJobUrlHash`
- `staleAfter`
- `expiresAt`
- `privateViewStatus`

Forbidden fields:

- Full resume text
- Full generated package text
- Phone / email
- 104 cookies / tokens / storage state
- Local absolute artifact paths
- Bearer tokens or local capability tokens

TDD first:

- `應徵` creates one request.
- Repeated `應徵` for the same active attempt reuses the request.
- Firestore payload sanitizer rejects forbidden fields.

Deferred TDD:

- Terminal attempts can create a new attempt.
- Same URL after 60 days creates a new attempt.
- Same URL with changed JD hash creates a new attempt.

Implementation:

- Add `應徵` action to high-fit 104 job cards.
- Add Firestore rules for `jobApplications/{uid}/requests/{applicationId}`.
- Add request creation helper in inbox JS.
- Defer automation-side lifecycle functions until the worker needs them.

Done criteria:

- Inbox tests pass.
- No private package content appears in Firestore fixtures.

## Phase 2 - Job Detail Snapshot Worker

Owner repo: `/home/hom/services/openclaw-job-notify-automation`

Goal:

Worker picks `requested` applications, fetches or reconstructs complete 104 job detail, snapshots JD, and moves to `fetching_resume`.

Private artifacts:

```text
/home/hom/services/openclaw-job-notify-profile/applications/<applicationId>/
  manifest.json
  jd.json
```

TDD first:

- Canonical URL removes tracking params.
- Closed or unavailable job moves to `blocked_job_closed` or `blocked_job_detail_unavailable`.
- Changed JD hash creates a new attempt when appropriate.
- JD snapshot is written only under private profile artifacts.

Implementation:

- Add `application_worker.py` entry point.
- Add `JobDetailProvider` port.
- Add private artifact repository.
- Update manifest with status and JD hash.

Done criteria:

- Unit tests pass.
- Dry-run on a fixture creates `manifest.json` and `jd.json`.
- Firestore contains only non-sensitive status and summary.

## Phase 3 - Resume Snapshot Integration

Owner repos:

- `/home/hom/services/openclaw-job-notify-automation`
- `/home/hom/services/104-resume-automation`

Goal:

Worker exports the source 104 online resume named `程式`, stores it privately, and handles auth blocks cleanly.

Private artifacts:

```text
source-resume.json
```

TDD first:

- Successful export stores private snapshot and moves to `generating_package`.
- Adapter ignores noisy `npm run` stdout and reads only explicit result files.
- Missing result file is a structured subprocess failure.
- Invalid result JSON is a structured subprocess failure.
- Non-zero exit with a valid blocked-auth result maps to `blocked_resume_fetch_auth_required`.
- Missing resume moves to `blocked_resume_not_found`.
- Login/OTP/captcha block moves to `blocked_resume_fetch_auth_required`.
- Worker does not retry auth-blocked requests forever.
- Auth-block writes a public-safe remediation event that can be sent through Claw Notify.
- Auth-block notification is rate-limited so a broken session does not spam.

Implementation:

- Add a stable CLI output contract to `104-resume-automation`.
- Add automation adapter that invokes the CLI with explicit file outputs, not stdout parsing:
  - `npm run resume:export -- --name 程式 --no-raw-text --output <tmp>/source-resume.json --result <tmp>/resume-export-result.json`
  - stdout/stderr are logs only and must never be parsed as the source of truth.
  - Python reads the result file and snapshot file after the subprocess exits.
  - The adapter treats missing result file, invalid result JSON, non-zero exit, timeout, and auth-block code as distinct failure classes.
- Add a stable result-file contract to `104-resume-automation`:

```json
{
  "ok": true,
  "status": "exported",
  "resumeName": "程式",
  "snapshotPath": "/tmp/source-resume.json",
  "screenshotPath": "screenshots/resume-export-程式.png",
  "sections": {
    "skillsSummaryChars": 188,
    "workSkillsChars": 60,
    "autobiographyChars": 1029
  }
}
```

Blocked auth result:

```json
{
  "ok": false,
  "status": "blocked_resume_fetch_auth_required",
  "reason": "login_or_otp_required"
}
```

- Never parse `npm run` stdout as JSON. `npm` output is allowed to be noisy.
- On `blocked_resume_fetch_auth_required`:
  - Update Firestore request status with `blockedReason: "104_auth_required"`.
  - Send one Claw Notify alert: `104 登入已過期，應徵包暫停產生`.
  - Include the safe repair action text: `在 /home/hom/services/104-resume-automation 執行 npm run auth:login-env`.
  - Do not include account, password, OTP, cookies, storage state, or local auth file contents.
  - Stop worker retries until a future run observes renewed auth or the user manually retries.
- Store a private audit entry in the application manifest with the raw internal error class, but keep public notification text generic.

Operational UX:

- The user's `應徵` click must not become a black hole.
- If auth is blocked, the request appears as blocked in the hosted inbox and sends a visible Claw Notify alert.
- The alert should point to the affected job title/company and say package generation will resume after re-auth.
- A later successful auth check can move the attempt back to `fetching_resume` or allow a manual retry action.

Done criteria:

- Fixture tests cover success and blocked auth.
- Tests cover noisy stdout, invalid result JSON file, missing result file, subprocess timeout, and non-zero exit.
- Real command still passes `npm run test` and `npx tsc --noEmit`.
- Auth-block path produces exactly one alert per request per cooldown window.

## Phase 4 - Package Generator, Reviewer, Validator

Owner repo: `/home/hom/services/openclaw-job-notify-automation`

Goal:

Generate copy-ready `技能摘要` and `自傳`, then independently review and validate them before marking package readiness.

Private artifacts:

```text
skill-summary.full.md
skill-summary.diff.md
autobiography.full.md
autobiography.diff.md
risk-review.md
application-package.md
manifest.json
```

Pipeline:

1. Generator produces only `skillsSummaryFull`, `autobiographyFull`, and rationale.
2. Reviewer independently receives source resume, JD, and generated output.
3. Reviewer emits `evidenceMap` and `riskFlags`.
4. Deterministic validator performs protected-field and protected-claim checks.
5. If clean, status moves toward private view generation.
6. If unsafe or ambiguous, status moves to `needs_manual_review`.

Manual review escape route:

- `needs_manual_review` must not be a dead end.
- The private package view must show:
  - risk flags and reviewer notes
  - copy-ready generated text as a draft
  - editable textareas for `技能摘要` and `自傳`
  - `儲存修正版`
  - `重新審查`
  - `取消此應徵包`
- Manual edits are saved as new artifact versions:

```text
skill-summary.manual-v<N>.md
autobiography.manual-v<N>.md
manual-review-note-v<N>.md
```

- Never require the user to edit Markdown files or manifest JSON directly.
- After `重新審查`, run reviewer + deterministic validator again.
- If clean, move to `package_ready`.
- If still blocked, remain `needs_manual_review` with updated risk notes.

Validator scope:

- Hard-block protected field changes.
- Hard-block new protected hard claims.
- Do not ask deterministic code to decide whether an unknown technology phrase is a synonym.
- Deterministic code handles protected fields/claims; Reviewer handles semantic equivalence with explicit confidence.
- Route ambiguity to warning or `needs_manual_review`.

Practical validator split:

- Reviewer extracts structured claims from generated text:
  - `protectedClaims`: company, school, certification, employment date, years, numeric result, award, management headcount, contact info.
  - `technologyClaims`: technology/tool/framework/platform terms.
  - `semanticEquivalence`: reviewer judgment for rewritten terms, with confidence and evidence.
- Deterministic validator hard-blocks only protected-claim violations it can match against source/JD evidence.
- Deterministic validator does not hard-block `technologyClaims` just because they are unseen.
- Unknown technology terms become warnings unless paired with protected assertions like years, certification, quantified achievement, or a claim of direct production use not present in evidence.
- Optional alias map is only a noise reducer for common terms. The system must still be acceptable if the alias map is tiny.

TDD first:

- Generator output with extra fields is rejected.
- Contact info changes are rejected.
- Employment history changes are rejected.
- New numeric claim not in source/JD is rejected.
- `AWS` / `Amazon Web Services` style wording is not a hard failure.
- Unknown technology wording becomes warning unless it claims years/certification/metric.
- Unknown technology with protected quantity, such as `5 years of Kubernetes`, moves to `needs_manual_review` when unsupported.
- Reviewer low-confidence semantic equivalence moves to warning or `needs_manual_review`, not automatic `package_ready`.
- Unsupported claim moves to `needs_manual_review`, not `package_ready`.
- `needs_manual_review` package can be opened in the private view.
- Saving manual edits creates versioned manual artifacts and never overwrites the original generated artifacts.
- Re-review after manual edits can move the package to `package_ready`.

Done criteria:

- Tests cover generator schema, reviewer schema, validator gates, and artifact output.
- Tests cover manual-review edit, versioning, and re-review.
- No generated full text is written to Firestore.

## Phase 5 - Tailnet Private Package View

Owner repos:

- `/home/hom/services/openclaw-job-notify-automation`
- `/home/hom/services/openclaw-notify-inbox`

Goal:

Expose copy-ready private package content through a private tailnet/local endpoint, not Firebase-hosted content.

Architecture decision:

- Firebase remains public notification/status shell.
- Private package view is top-level navigation to tailnet/local private endpoint.
- No Firebase-to-localhost fetch.
- No package content or bearer token in Firestore.

Private endpoint behavior:

- Bind only to tailnet/local interface.
- Accept `applicationId`.
- Resolve manifest under the private profile repo.
- Return HTML with copy buttons for:
  - `技能摘要`
  - `自傳`
- Include collapsed diff/risk review.
- Include actions or instructions for manual 104 submission.
- Include manual-review edit controls when status is `needs_manual_review`.
- Never expose source resume JSON, raw page text, cookies, tokens, phone, email, or arbitrary local paths.

Daemon:

- Implement the private view as an explicit daemon, not an unnamed side effect of the worker.
- Recommended first implementation: a small Python HTTP server in `openclaw-job-notify-automation`, for example `bin/application_private_view_server.py`.
- Use the standard library or the smallest existing dependency footprint first; avoid adding a full framework unless routing/forms become painful.
- The worker writes artifacts; the daemon reads artifacts and writes only manual-review revisions / submitted markers through a small repository API.
- Use atomic file writes for artifacts: write to `*.tmp`, flush/fsync when practical, then atomic rename to final path.
- Use per-application lock files for write operations: worker generation, manual review save, and submitted marker update.
- The daemon must never serve arbitrary files by path. It resolves `applicationId` to a manifest through the repository layer.
- Daemon management should be explicit: documented start command, optional systemd user service later, health endpoint returning public-safe status only, and heartbeat writer for `privateViewServiceLastSeenAt`.

Hosted UX:

- The hosted Firebase page cannot reliably preflight a user's current device reachability to the tailnet endpoint.
- Do not auto-redirect to the private endpoint.
- Show an explicit action panel:
  - `私密應徵包已產生`
  - `需要連上 Tailscale / 私有網路才能開啟`
  - `開啟私密應徵包`
  - `如果打不開，先開啟 Tailscale 後再回來點`
- The local bridge may publish a public-safe heartbeat, such as `privateViewServiceLastSeenAt`, so the hosted UI can distinguish service-down from device-not-connected.
- Device reachability remains unknowable from Firebase without making a cross-origin private-network request; do not claim otherwise.
- If service heartbeat is stale, show `package_ready_bridge_unavailable` before the user clicks.
- If heartbeat is healthy but the user's device is not on tailnet, the click may still fail at browser/network level; the UI must warn before navigation and keep the public status page usable after back navigation.

TDD first:

- Valid `applicationId` renders copy-ready fields.
- Unknown `applicationId` returns 404.
- Path traversal attempts fail.
- Response does not include forbidden private fields.
- Daemon health endpoint returns public-safe heartbeat data only.
- Concurrent worker/manual-review writes use lock/atomic write helpers.
- `needs_manual_review` renders editable fields and re-review actions.
- Hosted inbox status link opens private endpoint as top-level navigation.
- Hosted inbox does not auto-navigate to private endpoint.
- Hosted inbox shows Tailscale/private-network precondition text.
- Stale bridge heartbeat shows `package_ready_bridge_unavailable`.
- Healthy bridge heartbeat shows an explicit open button, not an automatic redirect.

Done criteria:

- Private endpoint works from an approved tailnet device.
- Daemon start command is documented.
- Daemon health/heartbeat is visible to the hosted shell without leaking private content.
- Firebase UI does not attempt localhost fetch.
- Package is usable without SSH or terminal file digging.
- Firebase UI degrades gracefully when the private endpoint is not reachable.

## Phase 6 - Manual Submission Tracking

Owner repos:

- `/home/hom/services/openclaw-notify-inbox`
- `/home/hom/services/openclaw-job-notify-automation`

Goal:

After the user manually submits on 104, the user can mark the application as submitted exactly once.

TDD first:

- `submitted_by_user` writes `submittedAt` only once.
- Repeated clicks update `lastSubmittedClickAt` but do not create a new submitted record.
- Submitted terminal attempt can be followed by a new attempt later.

Implementation:

- Add `我已送出` action in private package/status view.
- Write public-safe status update to Firestore.
- Append private submission record to profile repo.

Done criteria:

- Repeated marking is idempotent.
- Submitted records are eligible for 5-record batch notification.

## Phase 7 - Five-Record Batch Notify

Owner repo: `/home/hom/services/openclaw-job-notify-automation`

Goal:

Every 5 submitted records produce one Claw Notify summary without duplicates.

Outbox:

```text
applicationSummaryOutbox/{batchId}
```

Selection:

- Query submitted records where `batchNotifyId is null`.
- Order by `submittedAt`.
- Limit exactly 5.
- Create outbox with those exact record IDs.
- Send Notify.
- Mark the same 5 records with `batchNotifyId`.

TDD first:

- 4 submitted records do not send.
- 5 submitted records send exactly one batch.
- Retry uses existing outbox and does not recalculate membership.
- Repeated submitted click does not affect batch count.
- Failed send can retry without duplicate successful notifications.

Done criteria:

- Batch notification is deterministic and idempotent.
- Summary contains only public-safe job metadata and application statuses.

## Phase Order Recommendation

1. Phase 1: request model and `應徵` button.
2. Phase 2: JD snapshot worker.
3. Phase 3: resume snapshot integration.
4. Phase 4: generator/reviewer/validator.
5. Phase 5: tailnet private package view.
6. Phase 6: manual submitted tracking.
7. Phase 7: 5-record batch Notify.

Do not start Phase 4 until Phase 1-3 can create a complete private input bundle.
Do not call anything `package_ready` until Phase 5 makes copy-ready fields visible through the private view.
