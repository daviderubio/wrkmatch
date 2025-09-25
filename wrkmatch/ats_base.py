# wrkmatch/ats_base.py
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

@dataclass
class Job:
    source: str
    company: str
    title: str
    location: Optional[str]
    url: str
    posted_at: Optional[datetime] = None
    remote: Optional[bool] = None
    id: Optional[str] = None

class ATSClient:
    name: str  # override per subclass
    def fetch_jobs(self, company_slug: str, **kwargs) -> Iterable[Job]:
        raise NotImplementedError
