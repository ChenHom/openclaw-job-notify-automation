"""Pure job filtering and scoring rules for 104 job notifications."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime

TAICHUNG_AREAS = {
    "6001008007",  # 台中市西屯區
    "6001008006",  # 台中市北屯區
    "6001008005",  # 台中市北區
    "6001008004",  # 台中市西區
}

SEARCH_KEYWORDS = [
    "PHP 後端工程師",
    "Laravel PHP",
    "後端工程師",
    "Backend Engineer",
]

BACKEND_POSITIVE = (
    "後端",
    "backend",
    "back-end",
    "server",
    "api",
    "軟體工程師",
    "software engineer",
    "程式設計師",
    "programmer",
    "php",
    "laravel",
)
PHP_TERMS = ("php", "laravel", "symfony", "codeigniter")
REMOTE_TERMS = ("全遠端", "完全遠端", "純遠端", "remote", "fully remote")
NEGATIVE_ROLE_TERMS = (
    "前端",
    "frontend",
    "front-end",
    "flutter",
    "ios",
    "android",
    "mobile",
    "app工程師",
    "設計師",
    "designer",
    "業務",
    "sales",
    "行政",
    "客服",
    "審查",
    "content analyst",
    "數據分析師",
    "data analyst",
    "產品經理",
    "pm",
    "專案經理",
    "qa",
    "測試工程師",
    "devops",
    "sre",
)
EXCLUDED_STACK_TERMS = (
    "java",
    "spring",
    "spring boot",
    ".net",
    "c#",
    "c＃",
    "asp.net",
    "dotnet",
    "csharp",
)
GO_STACK_RE = re.compile(r"\b(?:go|golang|go\s+lang)\b", re.I)
LANGUAGE_TRANSFER_TERMS = (
    "可接受轉換語言",
    "接受轉換語言",
    "可轉換語言",
    "願意轉換語言",
    "其他語言也行",
    "其他語言亦可",
    "不限語言",
    "語言不限",
    "不限定語言",
    "不限制語言",
    "熟悉任一程式語言",
    "任一程式語言",
    "any programming language",
    "any language",
    "language agnostic",
    "open to other languages",
)
EXCLUDED_COMPANY_TERMS = (
    "愛勝科技",
    "戰國策",
    "精誠資訊",
    "藝珂人事",
    "藝珂",
)
EXCLUDED_ORG_TERMS = (
    "大學",
    "科技大學",
    "技術學院",
    "專科學校",
    "研究中心",
)

WEEKLY_CRITERIA = (
    "PHP／可轉語言後端、薪資 45K+、排除面議、更新 30 天內；"
    "Go/Golang 預設排除，除非 JD 明確接受轉換語言或其他語言也可；"
    "排序為 PHP 符合度優先，再看更新日期。"
)

TAG_KEYWORDS = {
    "php": ("php",),
    "laravel": ("laravel",),
    "api": ("api", "restful", "graphql", "sdk"),
    "redis": ("redis",),
    "mysql": ("mysql", "mariadb"),
    "postgresql": ("postgresql", "postgres"),
    "docker": ("docker",),
    "k8s": ("k8s", "kubernetes"),
    "ci_cd": ("ci/cd", "cicd", "gitlab ci", "自動化部署"),
    "testing": ("測試", "test", "phpunit", "自動化檢查"),
    "payment": ("支付", "金流", "交易"),
    "erp": ("erp", "eip", "bpm", "mes", "wms"),
    "backend": ("後端", "backend", "server"),
    "legacy": ("legacy", "舊系統", "重構", "modernization"),
    "remote": ("全遠端", "完全遠端", "純遠端", "remote"),
    "game": ("遊戲", "game"),
    "go_heavy": ("golang", "go lang"),
}


@dataclass(frozen=True)
class Job:
    group: str
    company: str
    title: str
    description: str
    salary: str
    location: str
    appear_date: str
    url: str
    job_no: str
    relevance: int
    source_keyword: str
    remote_type: int


def job_id_from_url(url: str) -> str:
    match = re.search(r"/job/([^/?#]+)", url or "")
    return match.group(1) if match else ""


def job_key(source: str, job_id: str) -> str:
    return f"{source}:{job_id}" if job_id else source


def compact(text: str) -> str:
    text = re.sub(r"\[\[\[|\]\]\]", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def item_text(item: dict) -> tuple[str, str, str, str]:
    title = compact(item.get("jobName") or "")
    desc = compact(item.get("description") or item.get("descSnippet") or "")
    hay_title = title.lower()
    hay = f"{title} {desc}".lower()
    return title, desc, hay_title, hay


def extract_tags(*parts: str) -> list[str]:
    hay = " ".join(compact(part).lower() for part in parts if part)
    tags = [tag for tag, terms in TAG_KEYWORDS.items() if any(term in hay for term in terms)]
    return sorted(set(tags))


def salary_text(item: dict) -> str:
    s10 = int(item.get("s10") or 0)
    low = int(item.get("salaryLow") or 0)
    high = int(item.get("salaryHigh") or 0)
    desc = item.get("salaryDesc") or ""
    if desc:
        return re.sub(r"^月薪\s*", "", desc).strip()
    if s10 == 50:
        if high and high != 9999999:
            return f"{low:,}～{high:,} 元"
        return f"{low:,} 元以上"
    if s10 == 60:
        if high and high != 9999999:
            return f"年薪 {low:,}～{high:,} 元"
        return f"年薪 {low:,} 元以上"
    return desc or "未標示"


def salary_ok(item: dict) -> bool:
    # 104 s10: 10=面議, 50=月薪, 60=年薪.
    s10 = int(item.get("s10") or 0)
    low = int(item.get("salaryLow") or 0)
    if s10 == 10:
        return False
    if s10 == 50:
        return low >= 45000
    if s10 == 60:
        return low >= 540000
    return False


def parse_date(value: str, tzinfo) -> datetime:
    try:
        return datetime.strptime(value or "", "%Y%m%d").replace(tzinfo=tzinfo)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=tzinfo)


def within_days(item: dict, now: datetime, days: int) -> bool:
    appeared = parse_date(str(item.get("appearDate") or ""), now.tzinfo)
    return (now - appeared).days <= days


def relevance_score(item: dict) -> int:
    _, _, hay_title, hay = item_text(item)
    score = 0
    if any(term in hay_title for term in PHP_TERMS):
        score += 100
    if any(term in hay for term in PHP_TERMS):
        score += 60
    if "後端" in hay_title or "backend" in hay_title or "back-end" in hay_title:
        score += 45
    if any(term in hay for term in ("後端", "backend", "back-end", "api", "server")):
        score += 25
    if any(term in hay_title for term in ("軟體工程師", "software engineer", "程式設計師", "programmer")):
        score += 12
    if any(term in hay_title for term in NEGATIVE_ROLE_TERMS):
        score -= 80
    return score


def allows_language_transfer(item: dict) -> bool:
    _, _, _, hay = item_text(item)
    return any(term in hay for term in LANGUAGE_TRANSFER_TERMS)


def stack_ok(item: dict) -> bool:
    _, _, _, hay = item_text(item)
    if any(term in hay for term in EXCLUDED_STACK_TERMS):
        return False
    if GO_STACK_RE.search(hay) and not allows_language_transfer(item):
        return False
    return True


def company_ok(item: dict) -> bool:
    company = compact(item.get("custName") or "")
    if any(term in company for term in EXCLUDED_COMPANY_TERMS):
        return False
    if any(term in company for term in EXCLUDED_ORG_TERMS):
        return False
    if item.get("isApplied") or item.get("applyDate"):
        return False
    return True


def role_ok(item: dict) -> bool:
    _, _, hay_title, hay = item_text(item)
    if any(term in hay_title for term in NEGATIVE_ROLE_TERMS):
        return False
    if not stack_ok(item):
        return False
    return any(term in hay for term in BACKEND_POSITIVE) and relevance_score(item) >= 20


def remote_ok(item: dict) -> bool:
    remote_type = int(item.get("remoteWorkType") or 0)
    tags = item.get("tags") or {}
    tag_text = json.dumps(tags, ensure_ascii=False).lower()
    hay = f"{item.get('jobName') or ''} {item.get('description') or ''} {tag_text}".lower()
    return remote_type == 1 or any(term in hay for term in REMOTE_TERMS)


def taichung_area_ok(item: dict) -> bool:
    area_no = str(item.get("jobAddrNo") or "")
    location = str(item.get("jobAddrNoDesc") or "")
    return area_no in TAICHUNG_AREAS or any(name in location for name in ("台中市西屯區", "台中市北屯區", "台中市北區", "台中市西區"))


def weekly_candidate_ok(item: dict, *, now: datetime, remote: bool, area: str | None) -> bool:
    if not within_days(item, now, 30):
        return False
    if not salary_ok(item):
        return False
    if not company_ok(item):
        return False
    if not role_ok(item):
        return False
    if remote and not remote_ok(item):
        return False
    if area and not taichung_area_ok(item):
        return False
    return True


def normalize_104_item(item: dict, *, group: str, keyword: str) -> Job:
    url = (item.get("link") or {}).get("job") or ""
    desc = compact(item.get("description") or item.get("descSnippet") or "")
    public_job_id = job_id_from_url(url) or str(item.get("jobNo") or url)
    return Job(
        group=group,
        company=compact(item.get("custName") or ""),
        title=compact(item.get("jobName") or ""),
        description=textwrap.shorten(desc, width=80, placeholder="…"),
        salary=salary_text(item),
        location=compact(item.get("jobAddrNoDesc") or ""),
        appear_date=str(item.get("appearDate") or ""),
        url=url,
        job_no=public_job_id,
        relevance=relevance_score(item),
        source_keyword=keyword,
        remote_type=int(item.get("remoteWorkType") or 0),
    )


def job_to_feedback_snapshot(job: Job, *, source_context: str) -> dict[str, object]:
    job_id = job.job_no or job_id_from_url(job.url)
    key = job_key("104", job_id)
    tags = extract_tags(job.title, job.description, job.location)
    if "台中" in job.location:
        tags.append("taichung")
    if job.remote_type == 1 and "remote" not in tags:
        tags.append("remote")
    return {
        "jobId": job_id,
        "jobKey": key,
        "source": "104",
        "sourceContext": source_context,
        "jobUrl": job.url,
        "company": job.company,
        "title": job.title,
        "salary": job.salary,
        "location": job.location,
        "tags": sorted(set(tags)),
    }
