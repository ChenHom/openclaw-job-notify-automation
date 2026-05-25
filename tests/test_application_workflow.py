from __future__ import annotations

import json
from pathlib import Path

from job_notify.application_workflow import (
    ApplicationArtifactRepository,
    ApplicationWorker,
    BLOCKED_JOB_DETAIL_UNAVAILABLE,
    BLOCKED_RESUME_FETCH_AUTH_REQUIRED,
    FETCHING_RESUME,
    GENERATING_PACKAGE,
    ResumeExportOutcome,
)
from job_notify.firestore_admin import FixtureApplicationStore


def request(**overrides):
    data = {
        "uid": "u1",
        "applicationId": "104_8abcd_程式",
        "status": "requested",
        "resumeName": "程式",
        "jobId": "8abcd",
        "jobUrl": "https://www.104.com.tw/job/8abcd?utm_source=notify",
        "title": "PHP 後端工程師",
        "company": "好公司",
        "sourceNotificationId": "n1",
    }
    data.update(overrides)
    return data


class FakeJobProvider:
    def __init__(self, snapshot=None, error=None):
        self._snapshot = snapshot
        self._error = error

    def snapshot(self, req):
        if self._error:
            raise self._error
        return self._snapshot or {
            "schemaVersion": 1,
            "source": "104_job",
            "applicationId": req["applicationId"],
            "jobUrl": req["jobUrl"],
            "title": req["title"],
            "company": req["company"],
            "fetchStatus": "metadata_only",
        }


class FakeResumeAdapter:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def export(self, *, application_id, output_path):
        self.calls.append((application_id, output_path))
        if self.outcome.ok:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps({"sections": {"autobiography": "ok"}}), encoding="utf-8")
        return self.outcome


def test_artifact_repository_keeps_applications_under_profile(tmp_path):
    repo = ApplicationArtifactRepository(tmp_path)

    app_dir = repo.application_dir("../bad/104:abc")

    assert app_dir.parent == tmp_path / "applications"
    assert app_dir.name == ".._bad_104:abc"


def test_worker_writes_jd_and_moves_to_fetching_resume_without_resume_adapter(tmp_path):
    req = request()
    store = FixtureApplicationStore([req])
    worker = ApplicationWorker(
        store=store,
        artifacts=ApplicationArtifactRepository(tmp_path),
        job_provider=FakeJobProvider(),
    )

    results = worker.run_once()

    assert results == [{"applicationId": "104_8abcd_程式", "status": FETCHING_RESUME}]
    jd = json.loads((tmp_path / "applications" / "104_8abcd_程式" / "jd.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "applications" / "104_8abcd_程式" / "manifest.json").read_text(encoding="utf-8"))
    assert jd["title"] == "PHP 後端工程師"
    assert manifest["status"] == FETCHING_RESUME
    assert store.status_updates[-1][1] == FETCHING_RESUME


def test_worker_blocks_job_detail_failures(tmp_path):
    req = request()
    store = FixtureApplicationStore([req])
    worker = ApplicationWorker(
        store=store,
        artifacts=ApplicationArtifactRepository(tmp_path),
        job_provider=FakeJobProvider(error=RuntimeError("closed")),
    )

    results = worker.run_once()

    assert results == [{"applicationId": "104_8abcd_程式", "status": BLOCKED_JOB_DETAIL_UNAVAILABLE}]
    assert store.status_updates[-1][1] == BLOCKED_JOB_DETAIL_UNAVAILABLE


def test_worker_exports_resume_and_moves_to_generating_package(tmp_path):
    req = request()
    store = FixtureApplicationStore([req])
    adapter = FakeResumeAdapter(ResumeExportOutcome(
        "exported",
        {
            "ok": True,
            "status": "exported",
            "resumeName": "程式",
            "sections": {"skillsSummaryChars": 1, "workSkillsChars": 2, "autobiographyChars": 3},
        },
        Path("source-resume.json"),
    ))
    worker = ApplicationWorker(
        store=store,
        artifacts=ApplicationArtifactRepository(tmp_path),
        job_provider=FakeJobProvider(),
        resume_adapter=adapter,
    )

    results = worker.run_once()

    assert results == [{"applicationId": "104_8abcd_程式", "status": GENERATING_PACKAGE}]
    source_resume = tmp_path / "applications" / "104_8abcd_程式" / "source-resume.json"
    assert source_resume.exists()
    manifest = json.loads((tmp_path / "applications" / "104_8abcd_程式" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == GENERATING_PACKAGE
    assert "snapshotPath" not in manifest["resumeExport"]
    assert store.status_updates[-1][1] == GENERATING_PACKAGE


def test_worker_maps_auth_blocked_resume_export(tmp_path):
    req = request()
    store = FixtureApplicationStore([req])
    adapter = FakeResumeAdapter(ResumeExportOutcome(
        BLOCKED_RESUME_FETCH_AUTH_REQUIRED,
        {"ok": False, "status": BLOCKED_RESUME_FETCH_AUTH_REQUIRED, "reason": "login_or_otp_required"},
    ))
    worker = ApplicationWorker(
        store=store,
        artifacts=ApplicationArtifactRepository(tmp_path),
        job_provider=FakeJobProvider(),
        resume_adapter=adapter,
    )

    results = worker.run_once()

    assert results == [{"applicationId": "104_8abcd_程式", "status": BLOCKED_RESUME_FETCH_AUTH_REQUIRED}]
    assert store.status_updates[-1][1] == BLOCKED_RESUME_FETCH_AUTH_REQUIRED


def test_fixture_application_store_can_filter_requested_items_by_limit():
    store = FixtureApplicationStore([
        request(applicationId="a1", status="requested"),
        request(applicationId="a2", status="generating_package"),
        request(applicationId="a3", status="requested"),
    ])

    assert [item["applicationId"] for item in store.list_requested(limit=1)] == ["a1"]
