# wrkmatch — Project Scaffold (GitHub Codespaces ready)

---

## Project tree

```
.
├── app/
│   └── streamlit_app.py
├── wrkmatch/
│   ├── __init__.py
│   ├── ats_clients.py
│   ├── fetch.py
│   ├── io_utils.py
│   ├── normalize.py
│   └── scoring.py
├── sample_data/
│   └── sample_connections.csv
├── .devcontainer/
│   └── devcontainer.json
├── .gitignore
├── requirements.txt
├── README.md
└── cli.py
```

---

## README.md

# wrkmatch

Find the companies where you have the **best shot**: cross your LinkedIn connections (CSV export) with public ATS job boards (Greenhouse, Lever, Ashby, Workable, Recruitee), then rank companies by **# contacts** × **# open roles**.

**Privacy‑first**: the app only processes your uploaded CSV in memory and queries public job feeds. No scraping, no LinkedIn API, no server‑side storage.

## Quickstart — GitHub Codespaces
1. Create a new GitHub repo and copy all files from this project.
2. Click **Code ▸ Codespaces ▸ Create codespace on main**.
3. After the container boots, the post‑create step installs dependencies.
4. Run the app:
   ```bash
   streamlit run app/streamlit_app.py --server.runOnSave true
   ```
5. Open the forwarded URL. Upload your **LinkedIn Connections CSV** and click **Scan companies**.

## Quickstart — Local

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Getting your LinkedIn CSV

LinkedIn → Settings & Privacy → Data privacy → Get a copy of your data → **Connections**. You’ll receive a CSV with names and (usually) current companies. It might take 24hrs for Linkedin to provide you with the data.

## What you’ll see

* **Connections KPIs:** total connections, unique companies, avg connections/company, plus top companies bar chart.
* **Jobs KPIs & trends:** total roles found, companies with roles, roles by ATS source, and a timeline by month (when dates are exposed).
* **Ranked targets:** a sortable table scoring companies by your contacts × open roles (+ optional senior‑role boost).
* **Details:** expand a company to see your contacts and role listings with links.
* **Downloads:** one‑click CSV exports of jobs and company scores.

## CLI (headless)

Run the pipeline and save CSV outputs without UI:

```bash
python cli.py sample_data/sample_connections.csv --out-dir out
```

Creates `out/company_scores.csv` and `out/jobs_report.csv`.

## Notes & limitations

* Some companies don’t expose a public job board or use an ATS not covered here.
* Name → ATS slug matching is heuristic; results vary by company naming conventions.
* Be mindful of rate limits. The scanner uses short timeouts and basic concurrency.

## License

MIT. 

---

## requirements.txt
```text
streamlit>=1.37
pandas>=2.0
requests>=2.31
rapidfuzz>=3.0
altair>=5.0
````

---

## .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.env
.venv/
.venv*/
.ipynb_checkpoints/
.pytest_cache/

# OS / IDE
.DS_Store
.idea/
.vscode/

# Streamlit
.streamlit/

# Outputs
out/
```

---

### How to use this scaffold

1. Create a **new GitHub repo** and paste these files with the same structure.
2. Open **Codespaces** from the repo (Code ▸ Codespaces ▸ Create).
3. In the built container, run `streamlit run app/streamlit_app.py` and open the forwarded port.
4. Upload your LinkedIn `Connections.csv` (or use `sample_data/sample_connections.csv` to demo), then click **Scan**.
