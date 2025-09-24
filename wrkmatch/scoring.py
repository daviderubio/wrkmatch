from __future__ import annotations
import pandas as pd

from .normalize import normalize_company_name


def compute_scores(connections_df: pd.DataFrame,
                   jobs_df: pd.DataFrame,
                   w_contacts: float = 1.5,
                   w_roles: float = 1.0,
                   senior_boost: float = 0.5) -> pd.DataFrame:
    contacts_per = (connections_df.assign(norm=lambda d: d["Company"].map(normalize_company_name))
                    .groupby("norm").size().rename("contacts").reset_index())

    if jobs_df.empty:
        jobs_per = pd.DataFrame({"norm": [], "roles": []})
        senior = pd.DataFrame({"norm": [], "senior_ratio": []})
    else:
        jobs_df = jobs_df.assign(norm=lambda d: d["company"].map(normalize_company_name))
        jobs_per = jobs_df.groupby("norm").size().rename("roles").reset_index()
        senior = (jobs_df.assign(is_senior=lambda d: d["title"].str.contains(r"senior|lead|head|principal|staff", case=False, regex=True))
                  .groupby("norm")["is_senior"].mean().fillna(0).rename("senior_ratio").reset_index())

    score = contacts_per.merge(jobs_per, on="norm", how="left").merge(senior, on="norm", how="left")
    score["roles"] = score["roles"].fillna(0)
    score["senior_ratio"] = score["senior_ratio"].fillna(0)
    score["score"] = score["contacts"] * w_contacts + score["roles"] * w_roles + score["senior_ratio"] * senior_boost

    # Display name: most common original company label for the norm
    name_map = (connections_df.assign(norm=lambda d: d["Company"].map(normalize_company_name))
                .groupby(["norm", "Company"]).size().reset_index(name="n")
                .sort_values(["norm", "n"], ascending=[True, False])
                .drop_duplicates("norm")[ ["norm", "Company"] ]
                .rename(columns={"Company": "display_company"}))

    score = score.merge(name_map, on="norm", how="left")
    return score.sort_values("score", ascending=False)