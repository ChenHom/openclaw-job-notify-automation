from __future__ import annotations

import json
from pathlib import Path

from job_notify.application_workflow import (
    ApplicationArtifactRepository,
    ApplicationPackageWorker,
    ApplicationWorker,
    BLOCKED_JOB_DETAIL_UNAVAILABLE,
    BLOCKED_RESUME_FETCH_AUTH_REQUIRED,
    ConservativePackageGenerator,
    FETCHING_RESUME,
    GENERATING_PACKAGE,
    JdAwarePackageGenerator,
    PACKAGE_READY_BRIDGE_UNAVAILABLE,
    ResumeExportOutcome,
    build_generated_resume_name,
)
from job_notify.application_private_view import render_package_view
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


def test_conservative_package_generator_copies_resume_fields_without_new_claims(tmp_path):
    req = request(status=GENERATING_PACKAGE)
    repo = ApplicationArtifactRepository(tmp_path)
    repo.update_manifest(req["applicationId"], {
        "schemaVersion": 1,
        "applicationId": req["applicationId"],
        "status": GENERATING_PACKAGE,
        "resumeName": "程式",
        "job": {"title": req["title"], "company": req["company"]},
    })
    repo.write_jd_snapshot(req, {
        "title": req["title"],
        "company": req["company"],
        "fetchStatus": "metadata_only",
    })
    repo.write_json(repo.source_resume_path(req["applicationId"]), {
        "sections": {
            "skillsSummary": "PHP\nLaravel",
            "autobiography": "原始自傳",
        }
    })

    result = ConservativePackageGenerator().generate(application_id=req["applicationId"], artifacts=repo)

    assert result.status == PACKAGE_READY_BRIDGE_UNAVAILABLE
    assert repo.skill_summary_full_path(req["applicationId"]).read_text(encoding="utf-8").strip() == "PHP\nLaravel"
    assert repo.autobiography_full_path(req["applicationId"]).read_text(encoding="utf-8").strip() == "原始自傳"
    package = repo.application_package_path(req["applicationId"]).read_text(encoding="utf-8")
    assert "PHP\nLaravel" in package
    assert "原始自傳" in package
    assert "No generated rewrite" in repo.risk_review_path(req["applicationId"]).read_text(encoding="utf-8")


def test_package_worker_moves_generating_package_to_bridge_unavailable(tmp_path):
    req = request(status=GENERATING_PACKAGE)
    store = FixtureApplicationStore([req])
    repo = ApplicationArtifactRepository(tmp_path)
    repo.update_manifest(req["applicationId"], {
        "applicationId": req["applicationId"],
        "status": GENERATING_PACKAGE,
        "resumeName": "程式",
        "job": {"title": req["title"], "company": req["company"]},
    })
    repo.write_jd_snapshot(req, {"title": req["title"], "company": req["company"], "fetchStatus": "metadata_only"})
    repo.write_json(repo.source_resume_path(req["applicationId"]), {
        "sections": {
            "skillsSummary": "PHP",
            "autobiography": "自傳",
        }
    })
    worker = ApplicationPackageWorker(store=store, artifacts=repo)

    results = worker.run_once()

    assert results == [{"applicationId": req["applicationId"], "status": PACKAGE_READY_BRIDGE_UNAVAILABLE}]
    assert store.status_updates[-1][1] == PACKAGE_READY_BRIDGE_UNAVAILABLE
    manifest = json.loads(repo.manifest_path(req["applicationId"]).read_text(encoding="utf-8"))
    assert manifest["status"] == PACKAGE_READY_BRIDGE_UNAVAILABLE
    assert manifest["package"]["files"]["applicationPackage"] == "application-package.md"


def test_jd_aware_package_generator_writes_resume_profile_and_allowed_fields(tmp_path):
    req = request(jobId="8rgy1", company="艾栩策略管理顧問", status=GENERATING_PACKAGE)
    repo = ApplicationArtifactRepository(tmp_path)
    repo.update_manifest(req["applicationId"], {
        "applicationId": req["applicationId"],
        "status": GENERATING_PACKAGE,
        "resumeName": "程式",
        "job": {"jobId": req["jobId"], "title": req["title"], "company": req["company"], "jobUrl": req["jobUrl"]},
    })
    repo.write_jd_snapshot(req, {
        "jobId": req["jobId"],
        "title": "Backend Engineer",
        "company": req["company"],
        "bodyText": "Laravel RESTful API MySQL Redis Queue Git Docker",
        "fetchStatus": "fetched",
    })
    repo.write_json(repo.source_resume_path(req["applicationId"]), {
        "sections": {
            "skillsSummary": "Vue\nPHP\nLaravel\nMySQL\nRedis\nGit",
            "workSkills": "軟體程式設計\n系統架構規劃",
            "autobiography": "我有金流平台開發維運、Laravel API、MySQL 效能改善、系統監控與既有系統重構經驗。",
        },
        "experiences": [
            {"company": "究境", "description": "導入 Laravel 框架\n重新規劃訂單及帳務流程\n搭配 Telegram 建立系統監控"},
            {"company": "揚鼎", "description": "導入 CodeIgniter\n透過 MySQL Explain 修正慢查詢"},
        ],
    })

    result = JdAwarePackageGenerator().generate(application_id=req["applicationId"], artifacts=repo)

    assert result.status == PACKAGE_READY_BRIDGE_UNAVAILABLE
    profile = json.loads(repo.resume_profile_path(req["applicationId"]).read_text(encoding="utf-8"))
    assert profile["generatedResumeName"] == "8rgy1_艾栩策略管理顧問"
    assert set(profile["allowlistedFields"]) == {"skillsSummary", "workSkills", "autobiography", "experiences"}
    assert "Laravel" in repo.skill_summary_full_path(req["applicationId"]).read_text(encoding="utf-8").splitlines()[0:3]
    assert "職能定位" in repo.autobiography_full_path(req["applicationId"]).read_text(encoding="utf-8")
    assert (repo.application_dir(req["applicationId"]) / "experiences" / "究境.full.md").exists()


def test_generated_resume_name_truncates_company_suffix_only():
    name = build_generated_resume_name("8rgy1", "非常非常非常非常非常長的公司名稱", max_length=12)

    assert name.startswith("8rgy1_")
    assert len(name) == 12


def test_private_package_view_renders_copy_ready_fields_without_source_snapshot(tmp_path):
    req = request(status=GENERATING_PACKAGE)
    repo = ApplicationArtifactRepository(tmp_path)
    repo.update_manifest(req["applicationId"], {
        "applicationId": req["applicationId"],
        "status": PACKAGE_READY_BRIDGE_UNAVAILABLE,
        "resumeName": "程式",
        "job": {"title": req["title"], "company": req["company"]},
        "package": {"status": PACKAGE_READY_BRIDGE_UNAVAILABLE},
    })
    repo.write_json(repo.resume_profile_path(req["applicationId"]), {
        "generatedResumeName": "8abcd_好公司",
        "job": {"title": req["title"], "company": req["company"]},
    })
    repo.write_text(repo.skill_summary_full_path(req["applicationId"]), "PHP\nLaravel")
    repo.write_text(repo.work_skills_full_path(req["applicationId"]), "後端 API 開發")
    repo.write_text(repo.autobiography_full_path(req["applicationId"]), "- 職能定位：PHP 後端")
    repo.write_text(repo.risk_review_path(req["applicationId"]), "Status: review required")

    view = render_package_view(application_id=req["applicationId"], artifacts=repo)

    assert view.status_code == 200
    assert "104 私密應徵包" in view.body
    assert "PHP\nLaravel" in view.body
    assert "source-resume.json" not in view.body
