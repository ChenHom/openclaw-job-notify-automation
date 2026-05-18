from __future__ import annotations

from datetime import datetime, timedelta, timezone

from job_notify.domain import (
    company_ok,
    remote_ok,
    salary_ok,
    stack_ok,
    taichung_area_ok,
    weekly_candidate_ok,
)


TAIPEI = timezone(timedelta(hours=8))


def item(**overrides):
    data = {
        "jobName": "PHP 後端工程師",
        "description": "Laravel API Redis MySQL",
        "descSnippet": "",
        "s10": 50,
        "salaryLow": 45000,
        "salaryHigh": 70000,
        "custName": "好公司",
        "jobAddrNo": "6001008007",
        "jobAddrNoDesc": "台中市西屯區",
        "appearDate": "20260518",
        "remoteWorkType": 1,
        "tags": {},
    }
    data.update(overrides)
    return data


def test_salary_rejects_negotiable_and_low_salary():
    assert salary_ok(item(s10=10, salaryLow=0)) is False
    assert salary_ok(item(s10=50, salaryLow=44000)) is False
    assert salary_ok(item(s10=60, salaryLow=539999)) is False
    assert salary_ok(item(s10=60, salaryLow=540000)) is True


def test_go_stack_is_rejected_unless_language_transfer_is_explicit():
    assert stack_ok(item(jobName="Golang 後端工程師", description="熟 Go / Redis / MySQL")) is False
    assert stack_ok(item(jobName="Backend Engineer", description="Go lang microservice")) is False
    assert stack_ok(item(jobName="Golang 後端工程師", description="可接受轉換語言，重視後端經驗")) is True
    assert stack_ok(item(jobName="Backend Engineer", description="其他語言也行，熟 API 設計")) is True


def test_company_and_org_exclusions():
    assert company_ok(item(custName="愛勝科技股份有限公司")) is False
    assert company_ok(item(custName="某某科技大學")) is False
    assert company_ok(item(custName="好公司", isApplied=True)) is False
    assert company_ok(item(custName="好公司")) is True


def test_location_and_remote_policy():
    assert taichung_area_ok(item(jobAddrNo="6001008007", jobAddrNoDesc="台中市西屯區")) is True
    assert taichung_area_ok(item(jobAddrNo="6001008001", jobAddrNoDesc="台中市中區")) is False
    assert remote_ok(item(remoteWorkType=1)) is True
    assert remote_ok(item(remoteWorkType=0, description="完全遠端工作")) is True


def test_weekly_candidate_policy_combines_common_rules():
    now = datetime(2026, 5, 18, tzinfo=TAIPEI)
    assert weekly_candidate_ok(item(), now=now, remote=True, area=None) is True
    assert weekly_candidate_ok(item(jobName="Golang 後端工程師", description="熟 Go"), now=now, remote=True, area=None) is False
    assert weekly_candidate_ok(item(appearDate="20260401"), now=now, remote=True, area=None) is False
    assert weekly_candidate_ok(item(jobAddrNo="6001008001", jobAddrNoDesc="台中市中區"), now=now, remote=False, area="6001008007") is False
