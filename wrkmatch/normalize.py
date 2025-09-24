import re
from typing import List

SUFFIXES = [
    " inc", " inc.", " llc", " ltd", " ltd.", " gmbh", " ag", " plc", " co", " co.",
    " corp", " corp.", " corporation", " company", " srl", " bv", " nv", " oy", " ab",
    " s.a.", " s.a", " s.p.a.", " spa", " sa", " sas", " kk", " kk."
]
NONWORD = re.compile(r"[^a-z0-9]")


def normalize_company_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = NONWORD.sub(" ", s)
    for suf in SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return re.sub(r"\s+", " ", s).strip()


def slug_candidates(name: str) -> List[str]:
    base = normalize_company_name(name)
    if not base:
        return []
    cands = {re.sub(r"\s+", "", base), re.sub(r"\s+", "-", base)}
    novowel = re.sub(r"[aeiou]", "", re.sub(r"\s+", "", base))
    cands.add(novowel)
    cands.add(base.split(" ")[0])
    return [c for c in cands if c]