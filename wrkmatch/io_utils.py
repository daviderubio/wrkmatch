from __future__ import annotations
import io
import re
from pathlib import Path
import pandas as pd

HEADER_HINTS = ("First Name", "Last Name")


def _read_text_any(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", errors="ignore")


def _clean_leading_notes(text: str) -> str:
    """LinkedIn Connections CSVs sometimes start with a 'Notes:' section before the real header.
    This trims everything before the line that contains the true header (First Name, Last Name, ...).
    """
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines[:300]):
        if all(h in line for h in HEADER_HINTS):
            header_idx = i
            break
    if header_idx is None:
        return text
    return "\n".join(lines[header_idx:])


def read_connections(file_or_path) -> pd.DataFrame:
    """Read a LinkedIn connections CSV, robust to the leading 'Notes:' preamble,
    various encodings, and varying column names. Returns a DataFrame with a 'Company' column.
    Accepts a file-like object or a path string.
    """
    # Load as text so we can strip the Notes preamble
    if isinstance(file_or_path, (str, bytes, Path)):
        path = Path(file_or_path)
        text = _clean_leading_notes(_read_text_any(path))
        df = pd.read_csv(io.StringIO(text))
    else:
        # file-like object: read bytes, clean, then parse
        b = file_or_path.read()
        if isinstance(b, bytes):
            raw = b
        else:
            raw = str(b).encode("utf-8", errors="ignore")
        for enc in ("utf-8", "utf-16", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        else:
            text = raw.decode("latin-1", errors="ignore")
        text = _clean_leading_notes(text)
        df = pd.read_csv(io.StringIO(text))

    # Normalize headers
    df.columns = [str(c).strip() for c in df.columns]

    # Derive Full Name if possible
    if "Full Name" not in df.columns:
        fn = [c for c in df.columns if "first" in c.lower()]
        ln = [c for c in df.columns if "last" in c.lower()]
        if fn and ln:
            df["Full Name"] = df[fn[0]].astype(str).str.strip() + " " + df[ln[0]].astype(str).str.strip()

    # Choose a company-like column
    comp_cols = [c for c in df.columns if c.lower() in {"company", "company name", "current company"}]
    if not comp_cols and "Position" in df.columns:
        # Try infer from ' at '
        df["Company"] = df["Position"].astype(str).str.extract(r" at (.+)$", expand=False)
        comp_cols = ["Company"]
    if not comp_cols:
        raise ValueError("Could not find a company column in your CSV. Try a different export or add a 'Company' column.")

    comp_col = comp_cols[0]
    df = df.rename(columns={comp_col: "Company"})
    df["Company"] = df["Company"].fillna("").astype(str)
    df = df[df["Company"].str.strip() != ""].copy()
    return df