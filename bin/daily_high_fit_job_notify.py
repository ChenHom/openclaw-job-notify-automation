#!/usr/bin/env python3
"""Send the daily 104 job report to Claw Notify."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_notify.config import add_config_args, load_config  # noqa: E402
from job_notify.notify_sender import send_firebase  # noqa: E402
from job_notify.domain import extract_tags, job_id_from_url, job_key  # noqa: E402
from job_notify.profile_repository import ProfileRepository  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))


@dataclass
class DailyJob:
    rank: int
    company: str = ""
    title: str = ""
    url: str = ""
    salary: str = ""
    location: str = ""
    updated: str = ""
    score: str = ""
    abilities: list[str] = field(default_factory=list)
    resume: list[str] = field(default_factory=list)
    intro: str = ""
    questions: list[str] = field(default_factory=list)


def count_recommendations(content: str) -> int:
    return len(re.findall(r"^##\s+推薦\s+\d+[:：]", content, flags=re.M))


def split_recommendation_blocks(content: str) -> list[tuple[int, str, str]]:
    matches = list(re.finditer(r"^##\s+推薦\s+(\d+)[:：]\s*(.+)$", content, flags=re.M))
    blocks: list[tuple[int, str, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end]
        block = re.split(r"^##\s+Seen\s+更新", block, maxsplit=1, flags=re.M)[0]
        blocks.append((int(match.group(1)), match.group(2).strip(), block.strip()))
    return blocks


def parse_list_after_heading(block: str, heading: str) -> list[str]:
    pattern = rf"^###\s+{re.escape(heading)}\s*$"
    m = re.search(pattern, block, flags=re.M)
    if not m:
        return []
    rest = block[m.end():]
    rest = re.split(r"^###\s+", rest, maxsplit=1, flags=re.M)[0]
    return [line[2:].strip() for line in rest.splitlines() if line.strip().startswith("- ")]


def parse_paragraph_after_heading(block: str, heading: str) -> str:
    pattern = rf"^###\s+{re.escape(heading)}\s*$"
    m = re.search(pattern, block, flags=re.M)
    if not m:
        return ""
    rest = block[m.end():]
    rest = re.split(r"^###\s+", rest, maxsplit=1, flags=re.M)[0]
    rest = re.sub(r"^>\s?", "", rest.strip(), flags=re.M).strip()
    return re.sub(r"\n{2,}", "\n", rest)


def parse_job(rank: int, heading: str, block: str) -> DailyJob:
    parts = [part.strip() for part in heading.split("｜", 1)]
    job = DailyJob(rank=rank, company=parts[0], title=parts[1] if len(parts) > 1 else "")
    fields = {
        "url": r"^-\s*連結[:：]\s*(.+)$",
        "salary": r"^-\s*薪資[:：]\s*(.+)$",
        "location": r"^-\s*地點[:：]\s*(.+)$",
        "updated": r"^-\s*更新日[:：]\s*(.+)$",
        "score": r"^-\s*契合分數[:：]\s*(.+)$",
    }
    for key, pattern in fields.items():
        m = re.search(pattern, block, flags=re.M)
        if m:
            setattr(job, key, m.group(1).strip())
    job.abilities = parse_list_after_heading(block, "JD 需要能力")
    job.resume = parse_list_after_heading(block, "履歷調整建議")
    job.intro = parse_paragraph_after_heading(block, "客製化自介角度")
    job.questions = parse_list_after_heading(block, "風險 / 面試提問")
    return job


def parse_jobs(content: str) -> list[DailyJob]:
    return [parse_job(rank, heading, block) for rank, heading, block in split_recommendation_blocks(content)]


def resolve_report_path(value: str | None, profile_repo: ProfileRepository, date_slug: str) -> Path:
    if not value:
        return profile_repo.daily_report_path(date_slug)
    candidate = Path(value)
    if candidate.exists() or candidate.suffix:
        return candidate
    return profile_repo.daily_report_path(value)


def esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def render_list(items: list[str]) -> str:
    if not items:
        return "<p class=\"job-empty\">未提供</p>"
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def render_job_card(job: DailyJob) -> str:
    title = esc(job.title or "開啟職缺")
    title_html = f'<a href="{esc(job.url)}" target="_blank" rel="noopener">{title}</a>' if job.url else title
    resume_text = "\n".join(f"- {item}" for item in job.resume)
    meta = [job.salary, job.location, f"更新 {job.updated}" if job.updated else "", f"契合 {job.score}" if job.score else ""]
    meta_html = "".join(f"<span>{esc(item)}</span>" for item in meta if item)
    copy_button = (
        f'<button type="button" class="copy-resume" data-copy-text="{esc(resume_text)}">複製履歷調整</button>'
        if resume_text else ""
    )
    return f"""
<article class="daily-job-card">
  <div class="daily-job-rank">{job.rank}</div>
  <div class="daily-job-main">
    <h3>{title_html}</h3>
    <div class="daily-job-company">{esc(job.company)}</div>
    <div class="daily-job-meta">{meta_html}</div>
    <section>
      <h4>JD 需要能力</h4>
      {render_list(job.abilities)}
    </section>
    <section class="resume-adjustment">
      <div class="section-head"><h4>履歷調整</h4>{copy_button}</div>
      {render_list(job.resume)}
    </section>
    <section>
      <h4>自介角度</h4>
      <p>{esc(job.intro) if job.intro else "未提供"}</p>
    </section>
    <section>
      <h4>風險 / 面試提問</h4>
      {render_list(job.questions)}
    </section>
  </div>
</article>""".strip()


def build_content_html(jobs: list[DailyJob]) -> str:
    if not jobs:
        return '<div class="daily-jobs-report"><p class="job-empty">今日沒有新的 104 每日職缺。</p></div>'
    cards = "\n".join(render_job_card(job) for job in jobs)
    return f'<div class="daily-jobs-report">{cards}</div>'


def build_summary(jobs: list[DailyJob]) -> str:
    if not jobs:
        return "今日沒有新的 104 每日職缺。"
    preview = "、".join(f"{job.company}｜{job.title}" for job in jobs[:3])
    suffix = "" if len(jobs) <= 3 else f" 等 {len(jobs)} 筆"
    return f"今日 104 每日職缺 {len(jobs)} 筆：{preview}{suffix}。"


def daily_job_payload(job: DailyJob) -> dict[str, object]:
    job_id = job_id_from_url(job.url)
    tags = extract_tags(job.title, job.company, job.salary, job.location, " ".join(job.abilities), job.intro)
    if "台中" in job.location:
        tags.append("taichung")
    if "遠端" in job.location:
        tags.append("remote")
    return {
        "rank": job.rank,
        "jobId": job_id,
        "jobKey": job_key("104", job_id),
        "source": "104",
        "sourceContext": "daily",
        "jobUrl": job.url,
        "company": job.company,
        "title": job.title,
        "salary": job.salary,
        "location": job.location,
        "updated": job.updated,
        "score": job.score,
        "skills": job.abilities,
        "tags": sorted(set(tags)),
    }


def build_notification_payload(report_path: Path, content: str, jobs: list[DailyJob], now: datetime) -> dict[str, object]:
    count = len(jobs)
    return {
        "id": f"daily-104-jobs-{report_path.stem}",
        "type": "jobs_104_daily",
        "source": "104",
        "sourceName": "104每日職缺",
        "language": "zh-Hant",
        "translationEnabled": False,
        "title": f"104每日職缺｜{count} 筆" if count else "104每日職缺｜今日無新增",
        "summary": build_summary(jobs),
        "url": "",
        "publishedAt": now.isoformat(),
        "tags": ["daily", "jobs", "104", "resume"],
        "notificationFrequency": "daily",
        "contentHtml": build_content_html(jobs),
        "contentMarkdown": content,
        "dailyJobs": [daily_job_payload(job) for job in jobs],
        "reportPath": str(report_path),
        "recommendationCount": count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", nargs="?", help="Path to report markdown. Defaults to today's report.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--send-empty", action="store_true", help="Also send a notification when no recommendation exists.")
    add_config_args(parser)
    args = parser.parse_args()

    config = load_config(profile_dir=args.profile_dir, config_file=args.config)
    profile_repo = ProfileRepository(config)
    now = datetime.now(TAIPEI)
    report_path = resolve_report_path(args.report, profile_repo, f"{now:%Y-%m-%d}")
    content = report_path.read_text(encoding="utf-8")
    jobs = parse_jobs(content)
    if not jobs and not args.send_empty:
        print(json.dumps({"ok": True, "skipped": True, "reason": "no recommendations", "report": str(report_path)}, ensure_ascii=False))
        return 0

    payload = build_notification_payload(report_path, content, jobs, now)
    send_firebase(payload, args.dry_run, config=config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
