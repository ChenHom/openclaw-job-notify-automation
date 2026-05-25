"""Private HTML view for generated 104 application packages."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .application_workflow import ApplicationArtifactRepository, PACKAGE_READY


FORBIDDEN_RESPONSE_MARKERS = (
    "rawPageText",
    "source-resume.json",
    "auth/104-storage-state",
    "cookie",
    "token",
)


@dataclass(frozen=True)
class PrivatePackageView:
    status_code: int
    content_type: str
    body: str


def render_health() -> PrivatePackageView:
    return PrivatePackageView(200, "application/json; charset=utf-8", json.dumps({"ok": True, "service": "104-application-private-view"}, ensure_ascii=False))


def render_package_view(*, application_id: str, artifacts: ApplicationArtifactRepository) -> PrivatePackageView:
    app_dir = artifacts.application_dir(application_id)
    manifest_path = artifacts.manifest_path(application_id)
    if not manifest_path.exists():
        return PrivatePackageView(404, "text/plain; charset=utf-8", "application package not found")

    manifest = artifacts.read_json(manifest_path)
    profile = artifacts.read_json(artifacts.resume_profile_path(application_id), {})
    skill_summary = read_text_if_exists(artifacts.skill_summary_full_path(application_id))
    work_skills = read_text_if_exists(artifacts.work_skills_full_path(application_id))
    autobiography = read_text_if_exists(artifacts.autobiography_full_path(application_id))
    risk_review = read_text_if_exists(artifacts.risk_review_path(application_id))
    package_status = str((manifest.get("package") or {}).get("status") or manifest.get("status") or "")
    resume_name = str(profile.get("generatedResumeName") or manifest.get("resumeName") or "")
    job = profile.get("job") or manifest.get("job") or {}
    body = build_package_html(
        application_id=application_id,
        package_status=package_status,
        resume_name=resume_name,
        job=job,
        skill_summary=skill_summary,
        work_skills=work_skills,
        autobiography=autobiography,
        risk_review=risk_review,
        app_dir=app_dir,
    )
    for marker in FORBIDDEN_RESPONSE_MARKERS:
        if marker.lower() in body.lower():
            return PrivatePackageView(500, "text/plain; charset=utf-8", "private view blocked unsafe response marker")
    return PrivatePackageView(200, "text/html; charset=utf-8", body)


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_package_html(
    *,
    application_id: str,
    package_status: str,
    resume_name: str,
    job: dict[str, Any],
    skill_summary: str,
    work_skills: str,
    autobiography: str,
    risk_review: str,
    app_dir: Path,
) -> str:
    def escaped_textarea(value: str) -> str:
        return html.escape(value, quote=False)

    status_note = "可審核" if package_status == PACKAGE_READY else "尚未標記 package_ready，請先審核內容"
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>104 私密應徵包 - {html.escape(application_id)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Noto Sans TC", sans-serif; margin: 24px; line-height: 1.55; color: #1f2933; }}
    main {{ max-width: 960px; margin: 0 auto; }}
    section {{ border: 1px solid #d7dee8; border-radius: 8px; padding: 16px; margin: 16px 0; }}
    textarea {{ width: 100%; min-height: 160px; box-sizing: border-box; font: 14px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }}
    button {{ padding: 8px 12px; border: 1px solid #9aa8b8; border-radius: 6px; background: #fff; cursor: pointer; }}
    .meta {{ color: #52616f; }}
    .warning {{ color: #9a3412; }}
  </style>
</head>
<body>
<main>
  <h1>104 私密應徵包</h1>
  <p class="meta">Application: {html.escape(application_id)} · 狀態：{html.escape(status_note)}</p>
  <p><strong>職缺：</strong>{html.escape(str(job.get("title", "")))} / {html.escape(str(job.get("company", "")))}</p>
  <p><strong>新履歷名稱：</strong>{html.escape(resume_name)}</p>
  <section>
    <h2>技能摘要</h2>
    <button data-copy="skills">複製</button>
    <textarea id="skills">{escaped_textarea(skill_summary)}</textarea>
  </section>
  <section>
    <h2>工作技能</h2>
    <button data-copy="workSkills">複製</button>
    <textarea id="workSkills">{escaped_textarea(work_skills)}</textarea>
  </section>
  <section>
    <h2>自傳</h2>
    <button data-copy="autobiography">複製</button>
    <textarea id="autobiography">{escaped_textarea(autobiography)}</textarea>
  </section>
  <section>
    <h2>Risk Review</h2>
    <pre>{html.escape(risk_review)}</pre>
  </section>
  <p class="warning">此頁只讀本機私密 artifact，不送出 104，也不修改線上履歷。</p>
</main>
<script>
document.querySelectorAll('button[data-copy]').forEach((button) => {{
  button.addEventListener('click', async () => {{
    const textarea = document.getElementById(button.dataset.copy);
    await navigator.clipboard.writeText(textarea.value);
    button.textContent = '已複製';
  }});
}});
</script>
</body>
</html>"""
