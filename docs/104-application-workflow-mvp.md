# 104 Application Workflow MVP

Date: 2026-05-21

## Goal

Claw Notify daily 104 high-fit job cards should let the user press `應徵`, then generate an application package based on the 104 online resume named `程式`.

The first version stops at package generation and manual submission tracking. It must not automatically modify 104 or submit an application.

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
- `failed`
- `cancelled`

## Application Package Artifacts

Private artifacts should live under the private profile boundary, not Firestore public notification payloads:

```text
applications/104_<jobId>_<timestamp>/
  manifest.json
  jd.json
  source-resume.json
  application-package.md
  skill-summary.patch.md
  autobiography.full.md
  autobiography.diff.md
  risk-review.md
```

Firestore and Notify payloads may include status, title, company, high-level summary, and artifact references. They must not include full resume text, phone, email, cookies, tokens, or 104 session data.

## Guardrails

- `應徵` creates or reuses an application request; it does not submit to 104.
- Duplicate active requests for the same canonical 104 job URL and resume name are rejected or reused.
- AI output is validated against a field allowlist: `skillsSummary`, `autobiography`.
- AI must not invent unverifiable experience, company names, titles, education, tenure, certificates, contact info, or salary data.
- `submitted_by_user` is idempotent. Repeated clicks count as one submitted record.
- Batch notification uses an outbox-style record so a retry does not send duplicate 5-job summaries.

## TDD Checklist

- `應徵` button writes one application request.
- Duplicate `應徵` clicks reuse the active request.
- Resume export targets `程式` and stays read-only.
- Application package includes complete paste-ready autobiography plus diff.
- AI patch containing fields outside `skillsSummary` / `autobiography` is rejected.
- Four submitted records do not send a batch notification.
- Five submitted records send exactly one batch notification.
- Retrying the batch notifier does not resend the same batch.
