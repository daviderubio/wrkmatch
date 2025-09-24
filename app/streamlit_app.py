from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st
import altair as alt

from wrkmatch import (
    read_connections,
    discover_and_fetch,
    compute_scores,
    normalize_company_name,
)

st.set_page_config(page_title="wrkmatch", layout="wide")
st.title("🔎 wrkmatch")
st.caption("Match your LinkedIn connections to companies with open roles on public job boards.")

# -------------------------
# Sidebar controls
# -------------------------
with st.sidebar:
    st.header("1) Upload your LinkedIn CSV")
    uploaded = st.file_uploader("Connections CSV", type=["csv"])  # not persisted server-side
    st.markdown("---")
    st.header("Options")
    w_contacts = st.slider("Weight: # contacts", 0.0, 3.0, 1.5, 0.1)
    w_roles = st.slider("Weight: # open roles", 0.0, 3.0, 1.0, 0.1)
    senior_boost = st.slider("Boost for senior-role prevalence", 0.0, 2.0, 0.5, 0.1)
    max_companies = st.slider("Max companies to scan", 10, 1000, 150, 10)

if uploaded is None:
    st.info("Upload your LinkedIn connections CSV to begin.")
    st.stop()

@st.cache_data(show_spinner=False)
def _read_connections_cached(buf):
    return read_connections(buf)

try:
    connections_df = _read_connections_cached(uploaded)
except Exception as e:
    st.error(f"Error reading CSV: {e}")
    st.stop()

st.success(f"Loaded {len(connections_df):,} connections with company info.")

# =========================
# Connections KPIs & charts
# =========================
with st.container():
    st.subheader("Connections — quick KPIs")
    comp_counts = (
        connections_df.assign(norm=lambda d: d["Company"].map(normalize_company_name))
        .groupby("norm").size().rename("n").reset_index()
    )
    total_connections = int(len(connections_df))
    unique_companies = int(comp_counts.shape[0])
    avg_per_company = float(comp_counts["n"].mean()) if not comp_counts.empty else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total connections", f"{total_connections:,}")
    c2.metric("Unique companies", f"{unique_companies:,}")
    c3.metric("Avg connections/company", f"{avg_per_company:.2f}")

    top_companies = comp_counts.sort_values("n", ascending=False).head(20)
    if not top_companies.empty:
        chart = (
            alt.Chart(top_companies)
            .mark_bar()
            .encode(
                x=alt.X("n:Q", title="# connections"),
                y=alt.Y("norm:N", sort="-x", title="Company (normalized)"),
            )
            .properties(height=500)
        )
        st.altair_chart(chart, use_container_width=True)

# -------------------------
# Build company list (limit to top N)
# -------------------------
by_company = (
    connections_df.groupby("Company")
    .size()
    .rename("n")
    .reset_index()
    .sort_values("n", ascending=False)
)
companies_all = by_company["Company"].tolist()
companies = companies_all[:max_companies]

st.header("2) Discover open roles at your contacts' companies")
st.caption(f"Scanning {len(companies)} of {len(companies_all)} companies (top by your connections).")
start = st.button("Scan companies for public job boards")

@st.cache_data(show_spinner=True)
def _discover_and_fetch_cached(companies_list):
    return discover_and_fetch(companies_list)

if start:
    with st.spinner("Probing ATS job boards (Greenhouse, Lever, Ashby, Workable, Recruitee)..."):
        jobs_df = _discover_and_fetch_cached(companies)
    st.session_state["jobs_df"] = jobs_df

jobs_df = st.session_state.get("jobs_df", pd.DataFrame())

if not jobs_df.empty:
    st.success(
        f"Found {len(jobs_df):,} job postings across {jobs_df['company'].nunique():,} of your companies."
    )

    # =========================
    # Jobs KPIs & trends
    # =========================
    with st.container():
        st.subheader("Jobs — KPIs & trends")
        jobs_df = jobs_df.copy()
        jobs_df["posted_at_dt"] = pd.to_datetime(jobs_df.get("posted_at"), errors="coerce")
        total_roles = int(len(jobs_df))
        companies_with_roles = int(jobs_df["company"].nunique())
        src_counts = (
            jobs_df.groupby("source")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        top_source_name = src_counts.iloc[0]["source"] if not src_counts.empty else "—"
        top_source_count = int(src_counts.iloc[0]["count"]) if not src_counts.empty else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total open roles discovered", f"{total_roles:,}")
        c2.metric("Companies with roles", f"{companies_with_roles:,}")
        c3.metric("Top source", f"{top_source_name} ({top_source_count:,})")

        chart_src = (
            alt.Chart(src_counts)
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="# roles"),
                y=alt.Y("source:N", sort="-x", title="Source"),
            )
        )
        st.altair_chart(chart_src, use_container_width=True)

        if jobs_df["posted_at_dt"].notna().any():
            ts = (
                jobs_df.dropna(subset=["posted_at_dt"])
                .assign(month=lambda d: d["posted_at_dt"].dt.to_period("M").dt.to_timestamp())
                .groupby("month")
                .size()
                .reset_index(name="count")
            )
            chart_ts = (
                alt.Chart(ts)
                .mark_line(point=True)
                .encode(
                    x=alt.X("month:T", title="Month"),
                    y=alt.Y("count:Q", title="# roles posted/updated"),
                    tooltip=["month:T", "count:Q"],
                )
            )
            st.altair_chart(chart_ts, use_container_width=True)
        else:
            st.caption("No posting dates exposed by the ATS feeds yet — timeline not available.")

    # -------------------------
    # Ranking
    # -------------------------
    st.header("3) Rank your best targets")
    score_df = compute_scores(connections_df, jobs_df, w_contacts=w_contacts, w_roles=w_roles, senior_boost=senior_boost)

    col1, col2, col3 = st.columns(3)
    with col1:
        min_contacts = st.number_input("Min contacts", 0, 100, 1)
    with col2:
        min_roles = st.number_input("Min open roles", 0, 1000, 1)
    with col3:
        top_k = st.number_input("Show top K", 1, 1000, 50)

    filtered = score_df[
        (score_df["contacts"] >= min_contacts) & (score_df["roles"] >= min_roles)
    ].head(top_k)

    st.subheader("Top companies (by your warm-intro potential)")
    st.dataframe(
        filtered[["display_company", "contacts", "roles", "senior_ratio", "score"]].rename(
            columns={
                "display_company": "Company",
                "roles": "Open roles",
                "senior_ratio": "% senior titles",
            }
        )
    )

    st.subheader("Company details & roles")
    for _, row in filtered.iterrows():
        comp = row["display_company"]
        with st.expander(
            f"{comp} — {int(row['contacts'])} contacts • {int(row['roles'])} roles • score {row['score']:.2f}"
        ):
            sample_contacts = (
                connections_df[connections_df["Company"].str.lower() == comp.lower()]
                .get("Full Name", pd.Series(["(names unavailable in CSV)"]))
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
            st.write(
                "**Your contacts**:",
                ", ".join(sample_contacts[:25]) + ("…" if len(sample_contacts) > 25 else ""),
            )

            comp_jobs = jobs_df[jobs_df["company"] == comp]
            if comp_jobs.empty:
                st.write("No public jobs found via ATS probes.")
            else:
                kw = st.text_input(f"Filter roles at {comp} (keyword)", key=f"kw_{comp}")
                loc = st.text_input(f"Filter by location at {comp}", key=f"loc_{comp}")
                view = comp_jobs
                if kw:
                    view = view[view["title"].str.contains(kw, case=False, na=False)]
                if loc:
                    view = view[view["location"].str.contains(loc, case=False, na=False)]
                st.dataframe(view[["title", "location", "department", "source", "url"]])
else:
    st.info("Click the scan button above to fetch public job postings for your companies.")
