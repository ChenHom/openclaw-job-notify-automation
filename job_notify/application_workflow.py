"""Minimal 104 application workflow worker.

This module owns the private artifact boundary for Phase 2/3/4:
Firestore request metadata is public-safe, while JD and resume snapshots are
written only under the private profile directory.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


REQUESTED = "requested"
FETCHING_JOB = "fetching_job"
FETCHING_RESUME = "fetching_resume"
GENERATING_PACKAGE = "generating_package"
PACKAGE_READY_BRIDGE_UNAVAILABLE = "package_ready_bridge_unavailable"
BLOCKED_JOB_DETAIL_UNAVAILABLE = "blocked_job_detail_unavailable"
BLOCKED_RESUME_FETCH_AUTH_REQUIRED = "blocked_resume_fetch_auth_required"
BLOCKED_RESUME_NOT_FOUND = "blocked_resume_not_found"
NEEDS_MANUAL_REVIEW = "needs_manual_review"
FAILED = "failed"


class ApplicationStore(Protocol):
    def list_requested(self, limit: int = 5) -> list[dict[str, Any]]: ...

    def list_generating_package(self, limit: int = 5) -> list[dict[str, Any]]: ...

    def update_status(self, request: dict[str, Any], status: str, extra: dict[str, Any] | None = None) -> None: ...


class JobDetailProvider(Protocol):
    def snapshot(self, request: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ResumeExportOutcome:
    status: str
    result: dict[str, Any]
    snapshot_path: Path | None = None

    @property
    def ok(self) -> bool:
        return self.status == "exported"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_job_url(url: str) -> str:
    if not url:
        return ""
    return re.sub(r"#.*$", "", url).strip()


def safe_application_id(application_id: str) -> str:
    value = re.sub(r"[^\w_.:-]", "_", application_id or "")
    if not value:
        raise ValueError("applicationId is required")
    return value[:140]


class ApplicationArtifactRepository:
    def __init__(self, profile_dir: Path):
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self.applications_dir = self.profile_dir / "applications"

    def application_dir(self, application_id: str) -> Path:
        app_dir = (self.applications_dir / safe_application_id(application_id)).resolve()
        if self.applications_dir.resolve() not in app_dir.parents:
            raise ValueError("application directory escapes profile applications root")
        return app_dir

    def manifest_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "manifest.json"

    def jd_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "jd.json"

    def source_resume_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "source-resume.json"

    def skill_summary_full_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "skill-summary.full.md"

    def skill_summary_diff_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "skill-summary.diff.md"

    def autobiography_full_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "autobiography.full.md"

    def autobiography_diff_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "autobiography.diff.md"

    def risk_review_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "risk-review.md"

    def application_package_path(self, application_id: str) -> Path:
        return self.application_dir(application_id) / "application-package.md"

    def write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.flush()
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)

    def write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
            tmp.write(text)
            if text and not text.endswith("\n"):
                tmp.write("\n")
            tmp.flush()
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)

    def read_json(self, path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.exists():
            return default or {}
        return json.loads(path.read_text(encoding="utf-8"))

    def update_manifest(self, application_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        path = self.manifest_path(application_id)
        current = self.read_json(path, {})
        merged = {**current, **patch, "updatedAt": utc_now_iso()}
        self.write_json(path, merged)
        return merged

    def write_jd_snapshot(self, request: dict[str, Any], snapshot: dict[str, Any]) -> Path:
        path = self.jd_path(request["applicationId"])
        self.write_json(path, snapshot)
        return path


class BasicJobDetailProvider:
    """Fetch a simple text snapshot, falling back to request metadata."""

    def __init__(self, *, timeout_seconds: int = 20, fetch_remote: bool = True):
        self.timeout_seconds = timeout_seconds
        self.fetch_remote = fetch_remote

    def snapshot(self, request: dict[str, Any]) -> dict[str, Any]:
        url = canonical_job_url(request.get("jobUrl", ""))
        if not url:
            raise RuntimeError("jobUrl is required")
        body_text = ""
        fetchStatus = "metadata_only"
        if self.fetch_remote:
            try:
                with urllib.request.urlopen(url, timeout=self.timeout_seconds) as res:
                    html = res.read().decode("utf-8", "replace")
                body_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()[:20_000]
                fetchStatus = "fetched"
            except Exception as exc:  # noqa: BLE001 - fallback snapshot is deliberate here.
                body_text = ""
                fetchStatus = f"fetch_failed:{type(exc).__name__}"
        return {
            "schemaVersion": 1,
            "source": "104_job",
            "applicationId": request["applicationId"],
            "jobUrl": url,
            "jobId": request.get("jobId", ""),
            "title": request.get("title", ""),
            "company": request.get("company", ""),
            "sourceNotificationId": request.get("sourceNotificationId", ""),
            "fetchedAt": utc_now_iso(),
            "fetchStatus": fetchStatus,
            "bodyText": body_text,
        }


class ResumeExportAdapter:
    def __init__(self, resume_automation_dir: Path, *, timeout_seconds: int = 90):
        self.resume_automation_dir = Path(resume_automation_dir).expanduser().resolve()
        self.timeout_seconds = timeout_seconds

    def export(self, *, application_id: str, output_path: Path) -> ResumeExportOutcome:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "resume-export-result.json"
            command = [
                "npm",
                "run",
                "resume:export",
                "--",
                "--name",
                "程式",
                "--no-raw-text",
                "--output",
                str(output_path),
                "--result",
                str(result_path),
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=self.resume_automation_dir,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return ResumeExportOutcome(FAILED, {"ok": False, "status": FAILED, "reason": "resume_export_timeout"})

            if not result_path.exists():
                return ResumeExportOutcome(
                    FAILED,
                    {
                        "ok": False,
                        "status": FAILED,
                        "reason": "missing_resume_export_result",
                        "returncode": completed.returncode,
                    },
                )
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return ResumeExportOutcome(FAILED, {"ok": False, "status": FAILED, "reason": "invalid_resume_export_result"})

        status = str(result.get("status") or FAILED)
        if result.get("ok") is True and status == "exported" and output_path.exists():
            return ResumeExportOutcome(status, result, output_path)
        return ResumeExportOutcome(status, result)


@dataclass(frozen=True)
class ApplicationPackageResult:
    status: str
    files: dict[str, str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return self.status == PACKAGE_READY_BRIDGE_UNAVAILABLE


class ConservativePackageGenerator:
    """Create copy-ready private package artifacts without inventing claims."""

    def generate(self, *, application_id: str, artifacts: ApplicationArtifactRepository) -> ApplicationPackageResult:
        manifest = artifacts.read_json(artifacts.manifest_path(application_id), {})
        jd = artifacts.read_json(artifacts.jd_path(application_id), {})
        source_resume = artifacts.read_json(artifacts.source_resume_path(application_id), {})
        sections = source_resume.get("sections") or {}
        skills_summary = normalize_multiline_text(str(sections.get("skillsSummary") or ""))
        autobiography = normalize_multiline_text(str(sections.get("autobiography") or ""))
        if not skills_summary or not autobiography:
            return ApplicationPackageResult(
                NEEDS_MANUAL_REVIEW,
                {},
                ["source_resume_missing_required_sections"],
            )

        risk_review = build_conservative_risk_review(jd)
        package = build_application_package(
            manifest=manifest,
            jd=jd,
            skills_summary=skills_summary,
            autobiography=autobiography,
            risk_review=risk_review,
        )
        writes = {
            "skillSummaryFull": artifacts.skill_summary_full_path(application_id),
            "skillSummaryDiff": artifacts.skill_summary_diff_path(application_id),
            "autobiographyFull": artifacts.autobiography_full_path(application_id),
            "autobiographyDiff": artifacts.autobiography_diff_path(application_id),
            "riskReview": artifacts.risk_review_path(application_id),
            "applicationPackage": artifacts.application_package_path(application_id),
        }
        artifacts.write_text(writes["skillSummaryFull"], skills_summary)
        artifacts.write_text(writes["skillSummaryDiff"], "No generated rewrite. Source field copied unchanged for MVP safety.\n")
        artifacts.write_text(writes["autobiographyFull"], autobiography)
        artifacts.write_text(writes["autobiographyDiff"], "No generated rewrite. Source field copied unchanged for MVP safety.\n")
        artifacts.write_text(writes["riskReview"], risk_review)
        artifacts.write_text(writes["applicationPackage"], package)
        return ApplicationPackageResult(
            PACKAGE_READY_BRIDGE_UNAVAILABLE,
            {key: path.name for key, path in writes.items()},
            ["private_view_bridge_not_implemented"],
        )


class ApplicationPackageWorker:
    def __init__(
        self,
        *,
        store: ApplicationStore,
        artifacts: ApplicationArtifactRepository,
        generator: ConservativePackageGenerator | None = None,
    ):
        self.store = store
        self.artifacts = artifacts
        self.generator = generator or ConservativePackageGenerator()

    def run_once(self, limit: int = 5) -> list[dict[str, Any]]:
        return [self.process_request(request) for request in self.store.list_generating_package(limit)]

    def process_request(self, request: dict[str, Any]) -> dict[str, Any]:
        application_id = request["applicationId"]
        result = self.generator.generate(application_id=application_id, artifacts=self.artifacts)
        self.store.update_status(request, result.status, {
            "updatedAt": utc_now_iso(),
            "packageStatus": result.status,
            "packageWarnings": result.warnings,
        })
        self.artifacts.update_manifest(application_id, {
            "status": result.status,
            "package": {
                "status": result.status,
                "files": result.files,
                "warnings": result.warnings,
            },
        })
        return {"applicationId": application_id, "status": result.status}


class ApplicationWorker:
    def __init__(
        self,
        *,
        store: ApplicationStore,
        artifacts: ApplicationArtifactRepository,
        job_provider: JobDetailProvider,
        resume_adapter: ResumeExportAdapter | None = None,
    ):
        self.store = store
        self.artifacts = artifacts
        self.job_provider = job_provider
        self.resume_adapter = resume_adapter

    def run_once(self, limit: int = 5) -> list[dict[str, Any]]:
        return [self.process_request(request) for request in self.store.list_requested(limit)]

    def process_request(self, request: dict[str, Any]) -> dict[str, Any]:
        application_id = request["applicationId"]
        self.store.update_status(request, FETCHING_JOB, {"updatedAt": utc_now_iso()})
        self.artifacts.update_manifest(application_id, {
            "schemaVersion": 1,
            "applicationId": application_id,
            "status": FETCHING_JOB,
            "resumeName": request.get("resumeName", "程式"),
            "job": public_job_manifest(request),
            "createdAt": request.get("createdAt") or utc_now_iso(),
        })

        try:
            jd_snapshot = self.job_provider.snapshot(request)
        except Exception as exc:  # noqa: BLE001 - status must be durable.
            self.store.update_status(request, BLOCKED_JOB_DETAIL_UNAVAILABLE, {"blockedReason": "job_detail_unavailable", "updatedAt": utc_now_iso()})
            self.artifacts.update_manifest(application_id, {"status": BLOCKED_JOB_DETAIL_UNAVAILABLE, "blockedReason": type(exc).__name__})
            return {"applicationId": application_id, "status": BLOCKED_JOB_DETAIL_UNAVAILABLE}

        self.artifacts.write_jd_snapshot(request, jd_snapshot)
        self.store.update_status(request, FETCHING_RESUME, {"updatedAt": utc_now_iso()})
        self.artifacts.update_manifest(application_id, {"status": FETCHING_RESUME, "jdSnapshotStatus": jd_snapshot.get("fetchStatus", "")})

        if not self.resume_adapter:
            return {"applicationId": application_id, "status": FETCHING_RESUME}

        outcome = self.resume_adapter.export(
            application_id=application_id,
            output_path=self.artifacts.source_resume_path(application_id),
        )
        if outcome.ok:
            self.store.update_status(request, GENERATING_PACKAGE, {"updatedAt": utc_now_iso()})
            self.artifacts.update_manifest(application_id, {
                "status": GENERATING_PACKAGE,
                "resumeExport": public_resume_export_result(outcome.result),
            })
            return {"applicationId": application_id, "status": GENERATING_PACKAGE}

        status = normalize_resume_failure_status(outcome.status)
        self.store.update_status(request, status, {"blockedReason": outcome.result.get("reason", "resume_export_failed"), "updatedAt": utc_now_iso()})
        self.artifacts.update_manifest(application_id, {"status": status, "resumeExport": outcome.result})
        return {"applicationId": application_id, "status": status}


def public_job_manifest(request: dict[str, Any]) -> dict[str, str]:
    return {
        "jobId": str(request.get("jobId", "")),
        "jobUrl": canonical_job_url(str(request.get("jobUrl", ""))),
        "title": str(request.get("title", "")),
        "company": str(request.get("company", "")),
        "sourceNotificationId": str(request.get("sourceNotificationId", "")),
    }


def public_resume_export_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "exported",
        "resumeName": result.get("resumeName", "程式"),
        "sections": result.get("sections", {}),
    }


def normalize_resume_failure_status(status: str) -> str:
    if status in {BLOCKED_RESUME_FETCH_AUTH_REQUIRED, BLOCKED_RESUME_NOT_FOUND}:
        return status
    return FAILED


def normalize_multiline_text(value: str) -> str:
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def build_conservative_risk_review(jd: dict[str, Any]) -> str:
    fetch_status = jd.get("fetchStatus", "")
    warnings = ["- No generated rewrite was applied; source resume fields were copied unchanged."]
    if fetch_status and fetch_status != "fetched":
        warnings.append(f"- JD snapshot is limited: `{fetch_status}`.")
    return "\n".join([
        "# Risk Review",
        "",
        "Status: conservative MVP package.",
        "",
        "Checks:",
        "- Protected fields were not rewritten.",
        "- No new company, school, certification, employment date, years, numeric result, or contact claim was generated.",
        *warnings,
        "",
        "Decision: package can be reviewed privately, but remains behind the private-view bridge gate.",
    ])


def build_application_package(*, manifest: dict[str, Any], jd: dict[str, Any], skills_summary: str, autobiography: str, risk_review: str) -> str:
    job = manifest.get("job") or {}
    title = jd.get("title") or job.get("title") or ""
    company = jd.get("company") or job.get("company") or ""
    return "\n".join([
        "# 104 Application Package",
        "",
        f"- Application ID: `{manifest.get('applicationId', '')}`",
        f"- Job: {title}",
        f"- Company: {company}",
        f"- Resume: {manifest.get('resumeName', '程式')}",
        "- Package mode: conservative source-copy MVP",
        "",
        "## 技能摘要",
        "",
        skills_summary,
        "",
        "## 自傳",
        "",
        autobiography,
        "",
        "## Review",
        "",
        risk_review,
    ])
