# 104 Application Workflow MVP

Date: 2026-05-21

## Goal

Claw Notify daily 104 high-fit job cards should let the user press `應徵`, then generate an application package based on the 104 online resume named `程式`.

The first version stops at package generation and manual submission tracking. It must not automatically modify 104 or submit an application.

## Current Verdict After Red-Team Review

The original MVP scope was directionally right, but several claims were too vague to be safe:

- "Private boundary" must name the exact storage boundary and access rule.
- "Read-only export" must define what happens when the 104 session expires.
- "Patch/diff" must not pretend 104 can apply git-like patches.
- "Risk review" must have automatic gates, not just a warning document.
- "Package ready" needs a user-visible status page and expiry policy.
- "Five submitted records" must be computed from stable submitted records, not from clicks or counters.
- A hosted inbox cannot show local private artifacts without an authenticated local bridge; the bridge is MVP scope, not future work.
- AI self-review is not enough; generation and verification must be separate steps.
- Job URL identity alone is too coarse for reopened evergreen jobs; application attempts need their own lifecycle.

## Confirmed Product Decisions

- The notification card has one primary button: `應徵`.
- The application package uses the 104 online resume named `程式` as the source resume.
- 104 submissions must use online resume data, not PDF or attachment upload.
- AI may tailor only:
  - 技能摘要
  - 自傳
- The autobiography output should be a complete paste-ready version plus a diff.
- Application summary batches count only jobs the user marked as submitted.
- Every 5 submitted records should produce one Claw Notify summary.

## Phase 0 Read-Only Resume Export

Before building the workflow, `104-resume-automation` must be able to safely read the source resume:

```bash
cd /home/hom/services/104-resume-automation
npm run resume:export -- --name 程式 --no-raw-text
```

Expected output:

- `outputs/resume-export-程式.json`
- `screenshots/resume-export-程式.png`
- No 104 write action.
- No application submission.
- Console output should report lengths only, not print the full resume.

The JSON snapshot must include:

- `resumeName`
- `url`
- `sections.skillsSummary`
- `sections.workSkills`
- `sections.autobiography`

Session handling:

- The script uses Playwright `storageState` at `/home/hom/services/104-resume-automation/auth/104-storage-state.json`.
- The file is local-only and gitignored.
- If 104 redirects to login, asks for OTP, captcha, or blocks the session, the workflow must move to `blocked_resume_fetch_auth_required`.
- The MVP does not auto-refresh 104 login state. Manual re-authentication is required through `npm run auth:login-env`.
- A worker must not retry forever when blocked by authentication. It should write a blocked status and surface a clear repair action.

## MVP State Flow

1. `requested`
2. `fetching_job`
3. `fetching_resume`
4. `generating_package`
5. `package_ready`
6. `manual_apply_opened`
7. `submitted_by_user`
8. `batch_notified`

Failure or blocked states:

- `blocked_job_detail_unavailable`
- `blocked_resume_not_found`
- `blocked_resume_fetch_auth_required`
- `blocked_job_closed`
- `needs_manual_review`
- `expired`
- `failed`
- `cancelled`

Bridge states:

- `package_ready_bridge_unavailable`
- `package_ready`

`package_ready` means the user can see and copy the tailored fields in UI. If the local bridge is unavailable, the workflow must not call the package fully ready.

Timeouts:

- `requested`, `fetching_job`, `fetching_resume`, and `generating_package` should be treated as stale after 30 minutes without progress.
- `package_ready` should remain available for 14 days, then move to `expired` unless the user marks it submitted or cancelled.
- Expired packages stay in private local artifacts for audit, but should no longer appear as active application requests.

## Application Package Artifacts

Private artifacts live only under the local private profile repo:

```text
/home/hom/services/openclaw-job-notify-profile/applications/104_<jobId>_<timestamp>/
```

This is a local filesystem boundary on the user's machine. It is not Firebase Hosting, Firestore, Cloud Storage, or a public HTTP path.

Only local automation processes on this machine should read or write it. Firestore may store an opaque `applicationId` and non-sensitive summary, but not a direct file path containing private details.

```text
applications/104_<jobId>_<timestamp>/
  manifest.json
  jd.json
  source-resume.json
  application-package.md
  skill-summary.full.md
  skill-summary.diff.md
  autobiography.full.md
  autobiography.diff.md
  risk-review.md
```

Firestore and Notify payloads may include status, title, company, high-level summary, and artifact references. They must not include full resume text, phone, email, cookies, tokens, or 104 session data.

The user-facing package page should show copy-ready full text first:

- `技能摘要` complete paste-ready text with a copy button.
- `自傳` complete paste-ready text with a copy button.
- Diff is secondary audit evidence, not the primary human action surface.

MVP does not apply patches back to 104 automatically. If future automation writes back to 104, it must replace whole field values from `*.full.md` and verify by re-reading the page after save. It must not try to apply git-like patches to 104 rich-text fields.

## Package Display

Claw Notify job cards only need the `應徵` button.

After the request is created, the user should open a private application status page in `openclaw-notify-inbox` using the `applicationId`. That page shows:

- Current status.
- Job title, company, and original 104 URL.
- Package generation result.
- Copy-ready `技能摘要`.
- Copy-ready `自傳`.
- Diff and risk review collapsed below the copy-ready fields.
- Actions: open 104 manually, mark submitted, cancel.

The status page reads non-sensitive Firestore fields first, then requests private package content from a local bridge.

## Local Private Bridge

- Firebase Hosting / Firestore cannot read `/home/hom/services/openclaw-job-notify-profile`.
- Therefore, the MVP must include a local private bridge. Without it, the workflow is not usable enough to call "package ready".
- The bridge is a localhost-only HTTP service on the user's machine, for example `127.0.0.1:<port>`.
- It accepts a short-lived signed read token and an `applicationId`.
- It resolves `applicationId` through a local manifest under `/home/hom/services/openclaw-job-notify-profile/applications/...`.
- It returns only:
  - `applicationId`
  - `status`
  - `jobTitle`
  - `company`
  - `skillsSummaryFull`
  - `autobiographyFull`
  - `riskStatus`
  - `riskFlags`
- It must not return source resume JSON, raw page text, cookies, tokens, phone, email, or arbitrary local file paths.
- It should be read-only for MVP.
- If the bridge is unavailable, the status is `package_ready_bridge_unavailable`, and the UI should say the package exists but cannot be opened on this device/session yet.
- `package_ready` is reserved for packages that are visible in the UI with copy buttons.

Do not put full resume text into public Firestore notification documents.

## Guardrails

- `應徵` creates or reuses an application request; it does not submit to 104.
- Duplicate active requests for the same canonical 104 job URL and resume name are rejected or reused.
- AI output is validated against a field allowlist: `skillsSummary`, `autobiography`.
- AI must not invent unverifiable experience, company names, titles, education, tenure, certificates, contact info, or salary data.
- `submitted_by_user` is idempotent. Repeated clicks count as one submitted record.
- Batch notification uses an outbox-style record so a retry does not send duplicate 5-job summaries.

AI risk gates:

- The generator must output structured JSON with only `skillsSummaryFull`, `autobiographyFull`, and a concise rationale.
- A separate reviewer step must independently receive the source resume snapshot, JD snapshot, and generated fields.
- The reviewer outputs `evidenceMap` and `riskFlags`.
- The reviewer should use a separate prompt and may use a separate model/agent. It must not reuse the generator's self-reported evidence as truth.
- The deterministic validator then checks reviewer output against the original source data.
- Any output that mentions a company, title, technology, metric, tenure, education, certificate, or contact field not present in the source resume or JD evidence map is rejected.
- If reviewer or deterministic validation emits `unsupported_claim`, `contact_info_changed`, `employment_history_changed`, `education_changed`, or `salary_changed`, the package cannot move to `package_ready`; it moves to `needs_manual_review`.
- `risk-review.md` is an audit artifact. The blocking decision must be represented in machine-readable manifest fields, not only prose.

Submitted-record identity:

- The job identity key is `104:{canonicalJobUrlHash}:程式`.
- The application attempt key is `104:{canonicalJobUrlHash}:程式:{attemptStartedAt}`.
- A new `應徵` click should reuse an active attempt only if it is not terminal and is inside the active reuse window.
- Terminal states are `submitted_by_user`, `cancelled`, and `expired`.
- After a terminal state, the user may create a new attempt for the same URL.
- The default reuse window for non-terminal attempts is 14 days.
- For evergreen/reopened jobs, a new attempt after 60 days should be allowed even if the URL is identical.
- The worker should snapshot the JD on every attempt. If the same URL has changed title/company/JD hash, it must create a new attempt even inside the reuse window.
- `submitted_by_user` stores `submittedAt` once. Repeated clicks update `lastSubmittedClickAt` but do not create a new submitted record.
- Batch selection queries submitted records where `batchNotifyId is null`, ordered by `submittedAt`, limited to 5.
- A batch is created only from exactly 5 record IDs and stores those IDs before sending.
- After send succeeds, the same `batchNotifyId` is written back to those exact 5 records.
- Retrying a batch must use the existing outbox record. It must not recalculate membership from a counter.

## TDD Checklist

- `應徵` button writes one application request.
- Duplicate `應徵` clicks reuse the active request.
- Resume export targets `程式` and stays read-only.
- Expired or OTP/captcha-blocked 104 session moves to `blocked_resume_fetch_auth_required` and does not loop forever.
- Application package includes complete paste-ready autobiography plus diff.
- Application package UI prioritizes copy-ready full fields; diff is secondary.
- Local private bridge returns copy-ready `skillsSummaryFull` and `autobiographyFull` for a valid `applicationId`.
- Hosted inbox does not mark an application `package_ready` unless copy-ready fields are visible through the bridge.
- Bridge responses do not include raw source resume, raw page text, local private paths, phone, email, cookies, or tokens.
- AI output containing fields outside `skillsSummary` / `autobiography` is rejected.
- Generator and reviewer are separate steps; reviewer does not trust generator-provided evidence.
- AI output with unsupported claims moves to `needs_manual_review`, not `package_ready`.
- Firestore notification/request documents do not include full resume text, phone, email, cookies, tokens, or local private paths with sensitive contents.
- `package_ready` expires after the configured TTL when the user takes no action.
- Same URL within an active 14-day non-terminal attempt reuses the attempt.
- Same URL after submitted/cancelled/expired can create a new attempt.
- Same URL after 60 days can create a new attempt for evergreen/reopened jobs.
- Same URL with changed JD hash creates a new attempt.
- Four submitted records do not send a batch notification.
- Five submitted records send exactly one batch notification.
- Retrying the batch notifier does not resend the same batch.
- Repeated `submitted_by_user` clicks for the same application do not affect future 5-record batch boundaries.
