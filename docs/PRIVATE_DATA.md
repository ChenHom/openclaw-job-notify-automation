# Private Data

The engine is public-safe only when user-specific data is kept in a separate private profile directory or private repository.

## Suggested Private Profile Layout

```
openclaw-job-notify-profile/
  config.json
  resume-summary.md
  seen_jobs.json
  search_hints.json
  reports/
    daily/
    weekly/
  templates/
```

## What Belongs Here

- Personal job preferences.
- Resume summary or resume path.
- Seen/applied/excluded jobs.
- Generated search hints.
- Generated job reports.
- Production sender command.
- Firebase project settings for real deployment.

## What Does Not Belong In RAG

Runtime secrets and credentials should not be stored in RAG or memory. RAG is suitable for design decisions, SOPs, and project history, not for values used to authenticate or write production systems.

## Related Projects

- Public automation engine: `openclaw-job-notify-automation`.
- Production inbox / delivery surface: `openclaw-notify-inbox`.
- Private profile boundary for the automation engine: `openclaw-job-notify-profile`.

Do not move inbox UI code, Firebase deployment files, or production push sender implementation into the public engine. Do not move personal profile data into the inbox repo.
