# wrkmatch/ats_clients_more.py
import json, re, requests
from datetime import datetime
from typing import Iterable, List, Optional
from .ats_base import ATSClient, Job

DEFAULT_TIMEOUT = 15
HEADERS_JSON = {"Accept": "application/json"}

def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None

# ---------- SMARTRECRUITERS ----------
class SmartRecruitersClient(ATSClient):
    """
    Public endpoint:
      GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings?limit=100&offset=0
    """
    name = "smartrecruiters"
    BASE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
    JOB_URL = "https://jobs.smartrecruiters.com/{company}/{job_id}"

    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        jobs: List[Job] = []
        limit, offset = 100, 0
        while True:
            url = self.BASE.format(company=company_slug)
            r = requests.get(url, params={"limit": limit, "offset": offset},
                             headers=HEADERS_JSON, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            postings = data.get("content", [])
            for p in postings:
                jid = p.get("id")
                title = p.get("name")
                loc = None
                if p.get("location"):
                    parts = [p["location"].get(k) for k in ("city", "region", "country")]
                    loc = ", ".join([x for x in parts if x])
                posted = _dt(p.get("releasedDate"))
                url = p.get("ref", {}).get("jobAdUrl") or self.JOB_URL.format(company=company_slug, job_id=jid)
                jobs.append(Job(self.name, company_slug, title, loc, url, posted_at=posted, id=jid))
            if len(postings) < limit:
                break
            offset += limit
        return jobs

# ---------- PERSONIO ----------
class PersonioClient(ATSClient):
    """
    Public JSON:
      GET https://{subdomain}.jobs.personio.de/search.json?language=en
    `company_slug` = Personio subdomain.
    """
    name = "personio"
    BASE = "https://{sub}.jobs.personio.de/search.json"

    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        url = self.BASE.format(sub=company_slug)
        r = requests.get(url, params={"language": "en"}, headers=HEADERS_JSON, timeout=DEFAULT_TIMEOUT)
        if r.status_code == 404:  # some tenants don’t support language param
            r = requests.get(url, headers=HEADERS_JSON, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = data if isinstance(data, list) else data.get("positions", [])
        out: List[Job] = []
        for it in items:
            title = it.get("name") or it.get("title")
            location = it.get("office") or it.get("location")
            if isinstance(location, dict):
                loc = ", ".join(filter(None, [location.get("name"), location.get("country")]))
            else:
                loc = location
            posted = _dt(it.get("published_at") or it.get("created_at"))
            url = it.get("url") or it.get("link")
            jid = str(it.get("id")) if it.get("id") is not None else None
            # naive remote signal
            remote = None
            if "keywords" in it and isinstance(it["keywords"], list):
                remote = any("remote" in (k or "").lower() for k in it["keywords"])
            out.append(Job(self.name, company_slug, title, loc, url, posted_at=posted, remote=remote, id=jid))
        return out

# ---------- BAMBOOHR ----------
class BambooHRClient(ATSClient):
    """
    Public careers JSON:
      GET https://{subdomain}.bamboohr.com/careers/list
    """
    name = "bamboohr"
    BASE = "https://{sub}.bamboohr.com/careers/list"
    JOB_URL = "https://{sub}.bamboohr.com/careers/{job_id}"

    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        url = self.BASE.format(sub=company_slug)
        r = requests.get(url, headers=HEADERS_JSON, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = data.get("result", [])
        out: List[Job] = []
        for it in items:
            if str(it.get("jobOpeningStatus", "")).lower() != "open":
                continue
            jid = str(it.get("id"))
            title = it.get("jobOpeningName") or it.get("jobTitle") or it.get("title")
            loc = it.get("location") or it.get("locationCity")
            url = it.get("jobUrl") or self.JOB_URL.format(sub=company_slug, job_id=jid)
            posted = _dt(it.get("postedDate") or it.get("publishedDate"))
            out.append(Job(self.name, company_slug, title, loc, url, posted_at=posted, id=jid))
        return out

# ---------- WORKDAY (experimental CXS) ----------
class WorkdayCXSClient(ATSClient):
    """
    Many Workday tenants expose:
      POST https://{host}/wday/cxs/{tenant}/jobs  payload: {"limit":100,"offset":0,"searchText":""}
    Provide either:
      - company_slug="host/tenant"
      - or kwargs: careers_url="https://deloitte.wd3.myworkdayjobs.com/Deloitte"
      - or kwargs: host="deloitte.wd3.myworkdayjobs.com", tenant="Deloitte"
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
            r = requests.post(url, headers={**HEADERS_JSON, "Content-Type": "application/json"},
                              data=json.dumps(payload), timeout=DEFAULT_TIMEOUT)
            if r.status_code == 404:
                break  # disabled/tenant-specific; bail gracefully
            r.raise_for_status()
            data = r.json()
            postings = data.get("jobPostings", []) or data.get("positions", [])
            if not postings:
                break
            for p in postings:
                title = p.get("title")
                loc = p.get("locationsText") or (p.get("locations", [{}])[0].get("text") if p.get("locations") else None)
                posted = _dt(p.get("postedOn") or p.get("postedDate"))
                external_path = p.get("externalPath") or p.get("titleJobReqId")
                job_url = (f"https://{host}/en-US/{tenant}/job/{external_path}"
                           if external_path and "/job/" not in str(external_path)
                           else (f"https://{host}{external_path}" if external_path else f"https://{host}/{tenant}"))
                jid = str(p.get("id") or p.get("bulletFields", [{}])[0].get("text") or external_path)
                out.append(Job(self.name, tenant, title, loc, job_url, posted_at=posted, id=jid))
            if len(postings) < limit:
                break
            offset += limit
        return out
