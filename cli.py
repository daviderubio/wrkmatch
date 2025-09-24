from __future__ import annotations
import argparse
from pathlib import Path

from wrkmatch import read_connections, discover_and_fetch, compute_scores


def main():
    ap = argparse.ArgumentParser(description="wrkmatch CLI")
    ap.add_argument("connections_csv", help="Path to LinkedIn connections CSV")
    ap.add_argument("--out-dir", default="out", help="Directory to write outputs")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Reading connections…")
    connections_df = read_connections(args.connections_csv)
    companies = sorted(set(connections_df["Company"].dropna().astype(str).str.strip()))

    print(f"Scanning {len(companies)} companies for public job boards…")
    jobs_df = discover_and_fetch(companies)

    print("Scoring companies…")
    scores_df = compute_scores(connections_df, jobs_df)

    jobs_path = out_dir / "jobs_report.csv"
    scores_path = out_dir / "company_scores.csv"
    jobs_df.to_csv(jobs_path, index=False)
    scores_df.to_csv(scores_path, index=False)

    print(f"Wrote {jobs_path} and {scores_path}")


if __name__ == "__main__":
    main()