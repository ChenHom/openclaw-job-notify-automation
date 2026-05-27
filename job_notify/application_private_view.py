"""Private HTML view for generated 104 application packages."""

from __future__ import annotations

import html
import json
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .application_workflow import ApplicationArtifactRepository, NEEDS_MANUAL_REVIEW, PACKAGE_READY, utc_now_iso


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
    headers: dict[str, str] | None = None


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
    manual_note = read_text_if_exists(app_dir / "manual-review-note-latest.md")
    manifest_status = str(manifest.get("status") or "")
    package_status = manifest_status if manifest_status == PACKAGE_READY else str((manifest.get("package") or {}).get("status") or manifest_status)
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
        manual_note=manual_note,
        app_dir=app_dir,
    )
    for marker in FORBIDDEN_RESPONSE_MARKERS:
        if marker.lower() in body.lower():
            return PrivatePackageView(500, "text/plain; charset=utf-8", "private view blocked unsafe response marker")
    return PrivatePackageView(200, "text/html; charset=utf-8", body)


def handle_package_action(*, application_id: str, artifacts: ApplicationArtifactRepository, raw_body: bytes) -> PrivatePackageView:
    manifest_path = artifacts.manifest_path(application_id)
    if not manifest_path.exists():
        return PrivatePackageView(404, "text/plain; charset=utf-8", "application package not found")
    form = {key: values[-1] for key, values in urllib.parse.parse_qs(raw_body.decode("utf-8"), keep_blank_values=True).items()}
    action = form.get("action", "")
    if action == "approve":
        package = dict(artifacts.read_json(manifest_path).get("package") or {})
        package["status"] = PACKAGE_READY
        artifacts.update_manifest(application_id, {
            "status": PACKAGE_READY,
            "package": package,
            "review": {
                "status": "approved",
                "approvedAt": utc_now_iso(),
            },
        })
        return redirect_to_package(application_id)
    if action == "cancel":
        artifacts.update_manifest(application_id, {
            "status": "cancelled",
            "review": {
                "status": "cancelled",
                "cancelledAt": utc_now_iso(),
                "note": form.get("note", ""),
            },
        })
        return redirect_to_package(application_id)
    if action == "save_manual":
        save_manual_revision(application_id=application_id, artifacts=artifacts, form=form)
        return redirect_to_package(application_id)
    return PrivatePackageView(400, "text/plain; charset=utf-8", "unknown package action")


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def redirect_to_package(application_id: str) -> PrivatePackageView:
    safe_id = urllib.parse.quote(application_id, safe="")
    location = f"/package?applicationId={safe_id}"
    return PrivatePackageView(303, "text/plain; charset=utf-8", location, {"Location": location})


def next_manual_version(app_dir: Path) -> int:
    versions = []
    for path in app_dir.glob("autobiography.manual-v*.md"):
        try:
            versions.append(int(path.stem.split("-v")[-1]))
        except ValueError:
            continue
    return max(versions, default=0) + 1


def save_manual_revision(*, application_id: str, artifacts: ApplicationArtifactRepository, form: dict[str, str]) -> None:
    app_dir = artifacts.application_dir(application_id)
    version = next_manual_version(app_dir)
    skills = form.get("skillsSummary", "")
    work_skills = form.get("workSkills", "")
    autobiography = form.get("autobiography", "")
    note = form.get("note", "")
    artifacts.write_text(app_dir / f"skill-summary.manual-v{version}.md", skills)
    artifacts.write_text(app_dir / f"work-skills.manual-v{version}.md", work_skills)
    artifacts.write_text(app_dir / f"autobiography.manual-v{version}.md", autobiography)
    artifacts.write_text(app_dir / f"manual-review-note-v{version}.md", note)
    artifacts.write_text(app_dir / "manual-review-note-latest.md", note)
    artifacts.update_manifest(application_id, {
        "status": NEEDS_MANUAL_REVIEW,
        "manualReview": {
            "status": "manual_revision_saved",
            "version": version,
            "updatedAt": utc_now_iso(),
            "files": {
                "skillSummary": f"skill-summary.manual-v{version}.md",
                "workSkills": f"work-skills.manual-v{version}.md",
                "autobiography": f"autobiography.manual-v{version}.md",
                "note": f"manual-review-note-v{version}.md",
            },
        },
    })


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
    manual_note: str,
    app_dir: Path,
) -> str:
    def escaped_textarea(value: str) -> str:
        return html.escape(value, quote=False)

    status_note = "已確認，可進 P6 草稿建立" if package_status == PACKAGE_READY else "待審核"
    p6_next = ""
    if package_status == PACKAGE_READY:
        profile_path = app_dir / "resume-profile.json"
        p6_next = f"""
  <section>
    <h2>P6 下一步</h2>
    <p>已通過 P5 審核，可執行 guarded apply 建立或更新 104 線上履歷草稿；此步驟不會送出應徵。</p>
    <pre>cd /home/hom/services/104-resume-automation &amp;&amp; npm run resume:draft -- --profile {html.escape(str(profile_path))} --apply</pre>
  </section>"""
    action_url = f"/package/action?applicationId={html.escape(application_id, quote=True)}"
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
    .actions {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin: 16px 0; }}
    .primary {{ background:#0f766e; color:#fff; border-color:#0f766e; }}
    .danger {{ color:#991b1b; border-color:#fecaca; }}
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
  <form method="post" action="{action_url}">
  <section>
    <h2>技能摘要</h2>
    <button data-copy="skills">複製</button>
    <textarea id="skills" name="skillsSummary">{escaped_textarea(skill_summary)}</textarea>
  </section>
  <section>
    <h2>工作技能</h2>
    <button data-copy="workSkills">複製</button>
    <textarea id="workSkills" name="workSkills">{escaped_textarea(work_skills)}</textarea>
  </section>
  <section>
    <h2>自傳</h2>
    <button data-copy="autobiography">複製</button>
    <textarea id="autobiography" name="autobiography">{escaped_textarea(autobiography)}</textarea>
  </section>
  <section>
    <h2>Risk Review</h2>
    <pre>{html.escape(risk_review)}</pre>
  </section>
  <section>
    <h2>審核備註</h2>
    <textarea name="note">{escaped_textarea(manual_note)}</textarea>
  </section>
  {p6_next}
  <div class="actions">
    <button class="primary" type="submit" name="action" value="approve">確認，進入 P6</button>
    <button type="submit" name="action" value="save_manual">儲存手動修正版</button>
    <button class="danger" type="submit" name="action" value="cancel">取消此應徵包</button>
  </div>
  </form>
  <p class="warning">此頁只讀本機私密 artifact，不送出 104，也不修改線上履歷。</p>
</main>
<script>
document.querySelectorAll('button[data-copy]').forEach((button) => {{
  button.addEventListener('click', async (event) => {{
    event.preventDefault();
    const textarea = document.getElementById(button.dataset.copy);
    await navigator.clipboard.writeText(textarea.value);
    button.textContent = '已複製';
  }});
}});
</script>
</body>
</html>"""
