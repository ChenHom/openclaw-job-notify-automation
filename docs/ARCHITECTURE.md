# Architecture

## Scope

This repository is a public-safe engine for 104 job notification automation. It provides reusable filtering, feedback scoring, report generation, and adapter boundaries.

It does not store a user's resume, job history, production Firebase project, notification credentials, or operating roadmap.

## Project Boundary

There are two project responsibilities in the current Claw Notify job-notification setup:

- `openclaw-job-notify-automation`: decides what job information should become a notification. It owns 104 scraping/search orchestration, pure filtering/scoring rules, feedback profile computation, report generation, search hints, and payload assembly.
- `openclaw-notify-inbox`: decides how notifications are stored, pushed, displayed, and how feedback is collected. It owns Firestore notification documents, FCM delivery, PWA inbox screens, job detail pages, and feedback writes.

The private profile directory is attached to the automation engine as runtime config and state. It is intentionally outside the public engine repo and outside the inbox repo.


## Related Claw Notify Tech Flow

The broader Claw Notify system also sends non-job technical article notifications through the same inbox/delivery surface.

As of 2026-05-20, the engineering-source runner is still in the OpenClaw workspace (`bin/engineering_sources_notify.py`) while service-folder consolidation is being reviewed. Its contract with the inbox is:

- `tech_*` notification `url` points to the internal inbox detail page.
- `originalUrl` preserves the source article/archive URL.
- `summary` is a short Chinese list-card summary.
- `contentHtml` is the preferred full translated detail body.
- `sourceTextStatus` must mark whether the translation is full-page, archive-based, skipped, or truncated.
- Full translation should use structured article blocks and small translator-agent batches so headings, paragraphs, lists, quotes, images, captions, code, and future tables remain comparable to the original article while still using Claw Notify's own visual template.

This repo remains the public-safe job automation engine. Do not move private profile data or inbox deployment concerns into this repo during tech-flow consolidation.

Job notification payloads are not article-translation sources. Weekly 104 lists, daily 104 reports, and job-feedback weekly reports must set `language: zh-Hant` and `translationEnabled: false` so the shared inbox schema can route them without guessing.

## Layers

### Domain

- `job_notify.domain`: 104 job filtering, salary/location checks, job identity, feedback snapshot tags.
- `job_notify.feedback`: feedback normalization, long-term scoring, search hints, weekly markdown reports.
- `job_notify.search_hints`: applies boost/downrank hints to ranking.

Domain code should be deterministic and testable without Firebase, OpenClaw, or private files.

### Private Profile Boundary

- `job_notify.config`: resolves profile directory and runtime settings.
- `job_notify.profile_repository`: reads/writes private profile files such as seen jobs, search hints, resume summary, and reports.

### Adapter Boundary

- `job_notify.ports`: protocols for stores/senders/profile access.
- `job_notify.firestore_admin`: Firestore REST adapter and fixture store.
- `job_notify.notify_sender`: command sender and test senders.

### CLI Entrypoints

- `bin/104_job_notify.py`
- `bin/daily_high_fit_job_notify.py`
- `bin/job_feedback_profile.py`
- `bin/job_feedback_weekly_report.py`

All runtime-specific data should come from CLI args, environment variables, or private profile files.

## Data Flow

1. Weekly/daily scripts collect or parse jobs.
2. Domain rules normalize and score jobs.
3. Feedback scripts read feedback from Firestore or fixture JSON.
4. Profile scoring writes private search hints.
5. Later searches read private search hints and adjust ranking.
6. Notification payloads are sent through a configured sender command.
7. The inbox project persists the notification, sends FCM push, renders the inbox/detail views, and writes user feedback.

## Public vs Private

Public repo:

- Engine code.
- Tests and fixture data.
- Example config.
- Generic docs.

Private profile:

- Runtime config.
- Resume summary.
- Seen jobs.
- Generated hints.
- Generated reports.
- Production sender command.
