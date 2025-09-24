from __future__ import annotations
import datetime as _dt
from dataclasses import dataclass
from typing import Optional, Union, List

import requests

USER_AGENT = "wrkmatch/1.0 (+https://example.invalid)"
DEFAULT_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json, */*;q=0.1"}

@dataclass
class Job:
    company: str
    source: str
    title: str
    location: str
    department: str
    url: str
    posted_at: Optional[str] = None  # ISO8601 when possible


def _coerce_iso(dt: Union[int, float, str, None]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, (int, float)):
        # Heuristic: big number → ms since epoch
        sec = dt / 1000.0 if dt > 1e11 else float(dt)
        return _dt.datetime.utcfromtimestamp(sec).isoformat() + "Z"
    s = str(dt)
    return s if s else None


def _get_json(url: str, timeout: int = 6):
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
            return r.json()
    except requests.RequestException:
        return None
    return None


def greenhouse_jobs(slug: str) -> List[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    data = _get_json(url)
    jobs: List[Job] = []
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        for j in data["jobs"]:
            jobs.append(Job(
                company=(j.get("offices", [{}])[0] or {}).get("name", "") or slug,
                source="greenhouse",
                title=j.get("title", ""),
                location=(j.get("location") or {}).get("name", ""),
                department=(j.get("departments", [{}])[0] or {}).get("name", ""),
                url=j.get("absolute_url", ""),
                posted_at=_coerce_iso(j.get("updated_at") or j.get("created_at")),
            ))
    return jobs


def lever_jobs(slug: str) -> List[Job]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    data = _get_json(url)
    jobs: List[Job] = []
    if isinstance(data, list):
        for j in data:
            jobs.append(Job(
                company=j.get("categories", {}).get("team", "") or slug,
                source="lever",
                title=j.get("text", ""),
                location=j.get("categories", {}).get("location", ""),
                department=j.get("categories", {}).get("team", ""),
                url=j.get("hostedUrl", ""),
                posted_at=_coerce_iso(j.get("createdAt") or j.get("updatedAt")),
            ))
    return jobs


def ashby_jobs(slug: str) -> List[Job]:
    url = f"https://api.ashbyhq.com/job-board-api/postings?organizationSlug={slug}"
    data = _get_json(url)
    jobs: List[Job] = []
    if isinstance(data, dict) and isinstance(data.get("postings"), list):
        for p in data["postings"]:
            jobs.append(Job(
                company=p.get("organizationName", "") or slug,
                source="ashby",
                title=p.get("title", ""),
                location=p.get("locationName", ""),
                department=p.get("teamName", ""),
                url=p.get("jobUrl", ""),
                posted_at=_coerce_iso(p.get("updatedAt") or p.get("createdAt")),
            ))
    return jobs


def workable_jobs(slug: str) -> List[Job]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    data = _get_json(url)
    jobs: List[Job] = []
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        for j in data["jobs"]:
            jobs.append(Job(
                company=data.get("name", "") or slug,
                source="workable",
                title=j.get("title", ""),
                location=(j.get("locations") or [{}])[0].get("location", ""),
                department=j.get("department", ""),
                url=j.get("application_url", "") or j.get("url", ""),
                posted_at=_coerce_iso(j.get("published_on") or j.get("updated_at")),
            ))
    return jobs


def recruitee_jobs(slug: str) -> List[Job]:
    url = f"https://{slug}.recruitee.com/api/offers/"
    data = _get_json(url)
    jobs: List[Job] = []
    if isinstance(data, dict) and isinstance(data.get("offers"), list):
        for j in data["offers"]:
            jobs.append(Job(
                company=data.get("name", "") or slug,
                source="recruitee",
                title=j.get("title", ""),
                location=(j.get("locations") or [{}])[0].get("city", ""),
                department=(j.get("departments") or [""])[0],
                url=j.get("careers_url", "") or j.get("url", ""),
                posted_at=_coerce_iso(j.get("created_at") or j.get("updated_at")),
            ))
    return jobs

ATS_FUNCS = [greenhouse_jobs, lever_jobs, ashby_jobs, workable_jobs, recruitee_jobs]