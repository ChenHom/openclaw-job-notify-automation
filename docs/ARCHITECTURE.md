# Architecture

## Scope

This repository is a public-safe engine for 104 job notification automation. It provides reusable filtering, feedback scoring, report generation, and adapter boundaries.

It does not store a user's resume, job history, production Firebase project, notification credentials, or operating roadmap.

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

