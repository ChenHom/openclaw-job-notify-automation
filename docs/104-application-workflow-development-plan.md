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

Goal:

When the user presses `應徵` on a 104 high-fit job, create or reuse an application attempt without generating private content yet.

Data model:

```text
jobApplications/{uid}/requests/{applicationId}
```

Public-safe fields:

- `applicationId`
- `jobIdentityKey`
- `attemptKey`
- `status`
- `jobUrl`
- `canonicalJobUrlHash`
- `resumeName: "程式"`
- `sourceNotificationId`
- `title`
- `company`
- `createdAt`
- `updatedAt`
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
- Terminal attempts can create a new attempt.
- Same URL after 60 days creates a new attempt.
- Same URL with changed JD hash creates a new attempt.
- Firestore payload sanitizer rejects forbidden fields.

Implementation:

- Add `應徵` action to high-fit 104 job cards.
- Add Firestore rules for `jobApplications/{uid}/requests/{applicationId}`.
- Add request creation helper in inbox JS.
- Add automation-side domain functions for attempt identity and lifecycle.

Done criteria:

- Inbox tests pass.
- Automation domain tests pass.
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
- Missing resume moves to `blocked_resume_not_found`.
- Login/OTP/captcha block moves to `blocked_resume_fetch_auth_required`.
- Worker does not retry auth-blocked requests forever.

Implementation:

- Add a stable CLI output contract to `104-resume-automation`.
- Add automation adapter that invokes `npm run resume:export -- --name 程式 --no-raw-text`.
- Parse stdout/result JSON or error code.

Done criteria:

- Fixture tests cover success and blocked auth.
- Real command still passes `npm run test` and `npx tsc --noEmit`.

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

Validator scope:

- Hard-block protected field changes.
- Hard-block new protected hard claims.
- Do not hard-block ordinary unseen technology synonyms.
- Route ambiguity to warning or `needs_manual_review`.

TDD first:

- Generator output with extra fields is rejected.
- Contact info changes are rejected.
- Employment history changes are rejected.
- New numeric claim not in source/JD is rejected.
- `AWS` / `Amazon Web Services` style wording is not a hard failure.
- Unknown technology wording becomes warning unless it claims years/certification/metric.
- Unsupported claim moves to `needs_manual_review`, not `package_ready`.

Done criteria:

- Tests cover generator schema, reviewer schema, validator gates, and artifact output.
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
- Never expose source resume JSON, raw page text, cookies, tokens, phone, email, or arbitrary local paths.

TDD first:

- Valid `applicationId` renders copy-ready fields.
- Unknown `applicationId` returns 404.
- Path traversal attempts fail.
- Response does not include forbidden private fields.
- Hosted inbox status link opens private endpoint as top-level navigation.
- If endpoint is unreachable, status is `package_ready_bridge_unavailable`.

Done criteria:

- Private endpoint works from an approved tailnet device.
- Firebase UI does not attempt localhost fetch.
- Package is usable without SSH or terminal file digging.

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
