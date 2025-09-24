from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
import pandas as pd

from .normalize import slug_candidates
from .ats_clients import ATS_FUNCS, Job

def discover_and_fetch(companies: List[str], max_workers: int = 12) -> pd.DataFrame:
    """Probe known ATS endpoints for each company and return a normalized jobs DataFrame.
    Optimizations:
      - Early-exit per company after the first ATS that returns jobs.
      - Early-exit per slug candidate as soon as jobs are found.
    """
    results: Dict[str, List[Job]] = {}

    def try_company(company: str) -> Tuple[str, List[Job]]:
        jobs: List[Job] = []
        tried = set()

        # Try the most likely slug candidates first
        candidates = slug_candidates(company)
        # heuristic: check compact/dashed first (keep original order)
        candidates = list(dict.fromkeys(candidates))  # de-dupe preserve order

        for cand in candidates:
            if cand in tried:
                continue
            tried.add(cand)
            for func in ATS_FUNCS:
                try:
                    fetched = func(cand)
                except Exception:
                    fetched = []
                if fetched:
                    jobs.extend(fetched)
                    # Found the company's ATS; stop trying others
                    return (company, jobs)
        return (company, jobs)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(try_company, c): c for c in companies}
        for fut in as_completed(futs):
            c, jobs = fut.result()
            results[c] = jobs

    rows = []
    for comp, jobs in results.items():
        for j in jobs:
            rows.append({
                "company": comp,
                "posting_company": j.company,
                "source": j.source,
                "title": j.title,
                "location": j.location,
                "department": j.department,
                "url": j.url,
                "posted_at": j.posted_at,
            })
    return pd.DataFrame(rows)
