# wrkmatch/ats_clients_more.py
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterable, List, Optional, Any, Dict

import requests

from .ats_base import ATSClient, Job  # Job here is the ats_base dataclass used internally by these clients

DEFAULT_TIMEOUT = 15
HEADERS_JSON = {"Accept": "application/json"}
UA = {"User-Agent": "wrkmatch/1.0 (+https://example.invalid)"}


def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _safe_json(resp: requests.Response) -> Optional[Any]:
    """Return JSON if content-type is JSON and parsing succeeds, else None."""
    ctype = resp.headers.get("Content-Type", "")
    if "json" not in ctype.lower():
        return None
    try:
        return resp.json()
    except requests.JSONDecodeError:
        return None


# ---------- SMARTRECRUITERS ----------
class SmartRecruitersClient(ATSClient):
    """
    Public postings:
      LIST:   GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings?limit=100&offset=0
              -> content can be a list of dicts OR a list of string IDs
      DETAIL: GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings/{id}
    """
    name = "smartrecruiters"

    BASE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
    DETAIL = "https://api.smartrecruiters.com/v1/companies/{company}/postings/{job_id}"
    JOB_URL = "https://jobs.smartrecruiters.com/{company}/{job_id}"

    def _fetch_detail(self, company: str, jid: str) -> Optional[Dict[str, Any]]:
        durl = self.DETAIL.format(company=company, job_id=jid)
        dresp = requests.get(durl, headers={**HEADERS_JSON, **UA}, timeout=DEFAULT_TIMEOUT)
        if dresp.status_code != 200:
            return None
        return _safe_json(dresp)

    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        jobs: List[Job] = []
        limit = 100
        offset = 0

        while True:
            url = self.BASE.format(company=company_slug)
            resp = requests.get(
                url,
                params={"limit": limit, "offset": offset},
                headers={**HEADERS_JSON, **UA},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = _safe_json(resp)
            if not isinstance(data, dict):
                break

            postings = data.get("content", [])
            if not isinstance(postings, list):
                break

            for p in postings:
                # Case 1: p is a string ID -> fetch details
                if isinstance(p, str):
                    jid = p
                    det = self._fetch_detail(company_slug, jid) or {}
                    title = det.get("name")
                    loc = None
                    dloc = det.get("location") if isinstance(det.get("location"), dict) else None
                    if dloc:
                        parts = [dloc.get(k) for k in ("city", "region", "country")]
                        loc = ", ".join([x for x in parts if x])
                    posted = _dt(det.get("releasedDate"))
                    url = (det.get("ref") or {}).get("jobAdUrl") or self.JOB_URL.format(company=company_slug, job_id=jid)
                    jobs.append(Job(
                        source=self.name,
                        company=company_slug,
                        title=title,
                        location=loc,
                        url=url,
                        posted_at=posted,
                        id=jid,
                        remote=None,
                    ))
                    continue

                # Case 2: p is a dict -> use it directly
                if not isinstance(p, dict):
                    continue
                jid = p.get("id")
                title = p.get("name")
                loc = None
                ploc = p.get("location") if isinstance(p.get("location"), dict) else None
                if ploc:
                    parts = [ploc.get(k) for k in ("city", "region", "country")]
                    loc = ", ".join([x for x in parts if x])
                posted = _dt(p.get("releasedDate"))
                pref = p.get("ref") if isinstance(p.get("ref"), dict) else {}
                url = pref.get("jobAdUrl") or self.JOB_URL.format(company=company_slug, job_id=jid)
                jobs.append(Job(
                    source=self.name,
                    company=company_slug,
                    title=title,
                    location=loc,
                    url=url,
                    posted_at=posted,
                    id=jid,
                    remote=None,
                ))

            if len(postings) < limit:
                break
            offset += limit

        return jobs


# ---------- PERSONIO ----------
class PersonioClient(ATSClient):
    """
    Public search JSON:
      GET https://{subdomain}.jobs.personio.de/search.json?language=en
      (some tenants don’t support the language param; try without)
    """
    name = "personio"
    BASE = "https://{sub}.jobs.personio.de/search.json"

    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        url = self.BASE.format(sub=company_slug)
        r = requests.get(url, params={"language": "en"}, headers={**HEADERS_JSON, **UA}, timeout=DEFAULT_TIMEOUT)
        data = _safe_json(r)
        if data is None or r.status_code == 404:
            r = requests.get(url, headers={**HEADERS_JSON, **UA}, timeout=DEFAULT_TIMEOUT)
            data = _safe_json(r)
        if data is None:
            return []

        items = data if isinstance(data, list) else data.get("positions", [])
        out: List[Job] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            title = it.get("name") or it.get("title")
            location = it.get("office") or it.get("location")
            if isinstance(location, dict):
                loc = ", ".join(filter(None, [location.get("name"), location.get("country")]))
            else:
                loc = location
            posted = _dt(it.get("published_at") or it.get("created_at"))
            url = it.get("url") or it.get("link")
            jid = str(it.get("id")) if it.get("id") is not None else None
            remote = None
            if isinstance(it.get("keywords"), list):
                remote = any("remote" in (k or "").lower() for k in it["keywords"])
            out.append(Job(
                source=self.name, company=company_slug, title=title,
                location=loc, url=url, posted_at=posted, remote=remote, id=jid
            ))
        return out


# ---------- BAMBOOHR ----------
class BambooHRClient(ATSClient):
    """
    Public careers JSON (if enabled):
      GET https://{subdomain}.bamboohr.com/careers/list
    Many tenants disable the JSON and only expose HTML at /careers. We return [] in that case.
    """
    name = "bamboohr"
    BASE = "https://{sub}.bamboohr.com/careers/list"
    JOB_URL = "https://{sub}.bamboohr.com/careers/{job_id}"

    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        url = self.BASE.format(sub=company_slug)
        resp = requests.get(url, headers={**HEADERS_JSON, **UA}, timeout=DEFAULT_TIMEOUT)

        data = _safe_json(resp)
        if data is None:
            # Not JSON -> likely disabled. Return empty list gracefully.
            return []

        items = (data or {}).get("result", []) if isinstance(data, dict) else []
        jobs: List[Job] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            if str(it.get("jobOpeningStatus", "")).lower() != "open":
                continue
            jid = str(it.get("id"))
            title = it.get("jobOpeningName") or it.get("jobTitle") or it.get("title")
            loc = it.get("location") or it.get("locationCity")
            jurl = it.get("jobUrl") or self.JOB_URL.format(sub=company_slug, job_id=jid)
            posted = _dt(it.get("postedDate") or it.get("publishedDate"))
            jobs.append(Job(
                source=self.name, company=company_slug, title=title,
                location=loc, url=jurl, posted_at=posted, id=jid
            ))
        return jobs


# ---------- WORKDAY (Experimental CXS) ----------
class WorkdayCXSClient(ATSClient):
    """
    Many Workday tenants expose a JSON search endpoint:
      POST https://{host}/wday/cxs/{tenant}/jobs
      payload: {"limit":100,"offset":0,"searchText":""}
    Some tenants return 4xx/5xx; we return [] in that case.
    """
    name = "workday_cxs"
    JOBS_PATH = "/wday/cxs/{tenant}/jobs"

    def _infer_host_tenant(self, company_slug: str, **kwargs):
        host = kwargs.get("host"); tenant = kwargs.get("tenant")
        if host and tenant:
            return host, tenant
        careers_url = kwargs.get("careers_url")
        if careers_url:
            m = re.search(r"https?://([^/]+)/([^/?#]+)", careers_url)
            if m:
                return m.group(1), m.group(2)
        if "/" in company_slug:
            parts = company_slug.split("/", 1)
            return parts[0], parts[1]
        raise ValueError("Workday: provide careers_url or host+tenant (or 'host/tenant' as slug).")

    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        host, tenant = self._infer_host_tenant(company_slug, **kwargs)
        url = f"https://{host}{self.JOBS_PATH.format(tenant=tenant)}"
        out: List[Job] = []
        offset, limit = 0, 100

        while True:
            payload = {"limit": limit, "offset": offset, "searchText": ""}
            r = requests.post(
                url,
                headers={**HEADERS_JSON, **UA, "Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=DEFAULT_TIMEOUT,
            )

            if r.status_code >= 400:
                # Tenant disabled endpoint or server error -> return empty
                return []

            data = _safe_json(r)
            if not isinstance(data, dict):
                return []

            postings = data.get("jobPostings", []) or data.get("positions", [])
            if not postings:
                break

            for p in postings:
                if not isinstance(p, dict):
                    continue
                title = p.get("title")
                loc = p.get("locationsText") or (p.get("locations", [{}])[0].get("text") if p.get("locations") else None)
                posted = _dt(p.get("postedOn") or p.get("postedDate"))
                external_path = p.get("externalPath") or p.get("titleJobReqId")
                if external_path:
                    if "/job/" in str(external_path):
                        job_url = f"https://{host}{external_path}"
                    else:
                        job_url = f"https://{host}/en-US/{tenant}/job/{external_path}"
                else:
                    job_url = f"https://{host}/{tenant}"
                jid = str(p.get("id") or (p.get("bulletFields", [{}])[0].get("text") if p.get("bulletFields") else None) or external_path)
                out.append(Job(
                    source=self.name, company=tenant, title=title,
                    location=loc, url=job_url, posted_at=posted, id=jid
                ))

            if len(postings) < limit:
                break
            offset += limit

        return out