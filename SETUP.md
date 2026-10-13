# CourseCast setup

Run the starter locally before beginning your assigned task. Each teammate creates
an environment on their own laptop; `.venv` is not shared through Git.

The starter currently uses **synthetic demo data**. The collector and trained
forecasting model are not implemented yet. Postgres is not required to run the demo.

## 1. Get the repository

Install Git and Python first. Python **3.12** is recommended: the starter was checked
on that version. On Windows, enable the Python installer's **Add Python to PATH** option.

Accept your GitHub collaborator invitation if the repo is private. On the repo page,
click **Code → HTTPS** and copy its URL.

In a terminal, replace `REPO_URL` with that URL and run:

```text
git clone REPO_URL
```

Open the downloaded repository folder in VS Code with **File → Open Folder**.
Then choose **Terminal → New Terminal**. All commands below must run from the repo
root: the folder containing `requirements-dev.txt`, `backend/` and `frontend/`.

If you already cloned the repo, open your existing folder instead. The starter
files must be present on the branch you use. If the starter PR has not been merged,
ask the co-leads which branch to start from.

## 2. Windows setup (PowerShell)

Check Python:

```powershell
python --version
```

Create your local environment once:

```powershell
python -m venv .venv
```

Install the app and test dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

These commands use the environment's Python directly. **You do not need to run
`Activate.ps1` or change PowerShell's execution policy.**

### Run the checks

```powershell
.\.venv\Scripts\python.exe -m collector.validate_samples
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected results:

- Sample validation: `Validated 6 synthetic snapshots across 3 sections.`
- Tests: four tests pass and the output ends with `OK`.

A `StarletteDeprecationWarning` about `httpx` may appear with this dependency set.
It did not prevent the starter tests from passing.

### Start the backend

In your first terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Leave that terminal running. API documentation is at
<http://127.0.0.1:8000/docs>.

### Start the frontend

Open **Terminal → New Terminal**, make sure it is in the same repo root, and run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Leave this terminal running too. Open <http://localhost:8501> or the local URL
printed by Streamlit.

## 3. macOS / Linux setup

From the repo root:

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m collector.validate_samples
.venv/bin/python -m unittest discover -s tests -v
```

Start the backend in one terminal:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload
```

Start the frontend in a second terminal, also in the repo root:

```bash
.venv/bin/python -m streamlit run frontend/app.py
```

No environment activation is needed with these commands.

## 4. Check the demo

1. Open the frontend.
2. Keep the default section (`DEMO-225-A`) and default ticket: October 13, 2026,
   noon, America/Chicago.
3. Click **Show demo forecast**.
4. Expect approximately **83%** and a probability chart.
5. Select the closed demo section (`DEMO-341-A`) and submit again. Expect an
   unavailable-forecast message.

A stale-observation warning is expected when the fixed sample observation is more
than two hours old. The fixture dates are examples, not UIUC registration dates.
Tickets beyond the sample curve's end return unavailable; use the defaults for
this check. None of the demo numbers should guide real registration decisions.

Press **Ctrl+C** in each server terminal when you want to stop the app. The next
time you work, run the two server commands again; do not recreate `.venv`.

## 5. Before committing your work

Work on your own branch, agreed with the co-leads. From the correct shared starting
branch, create it with a descriptive name, for example:

```text
git switch -c your-name/task-name
```

Replace `your-name/task-name` with your own branch name. Review your changes:

```text
git status
```

`.venv/`, `__pycache__/` and real `.env` files should be ignored. `.env.example` is
safe to commit because it documents settings without real credentials. Never copy
another teammate's `.venv` or commit your own.

Stage the intended files, commit, push your branch and open a pull request for
review. If dependencies change, update the requirements file so teammates can
install the same dependencies. Installing modelling dependencies is a separate,
optional step documented in `modelling/README.md`.

## Quick fixes

- **`python` not found on Windows:** try `py -3.12 --version` and
  `py -3.12 -m venv .venv`. After creating the environment, use the explicit
  `.venv\Scripts\python.exe` commands above.
- **`requirements-dev.txt` or `backend` not found:** check that the terminal is in
  the repo root and that the starter files are on your current branch.
- **Frontend cannot reach the API:** start the backend and leave its terminal open.
  Refresh the frontend. The default backend address is `http://127.0.0.1:8000`.
- **Port already in use:** check whether your earlier server is still running.
  Stop that server with Ctrl+C before starting another copy.
- **Installation or tests fail:** share the full error in the team thread,
  along with your operating system and Python version.
