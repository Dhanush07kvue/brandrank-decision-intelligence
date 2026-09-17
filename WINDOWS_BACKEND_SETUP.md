# Windows Backend Setup

Run the FastAPI backend locally on Windows PowerShell with a project-local Python virtual environment.

## Prerequisites

- Windows 10 or 11
- Python 3.11 or newer
- PowerShell
- PostgreSQL 16 (for `BAI_STORAGE_MODE=dual` or `postgres`)

### PostgreSQL 16 quick setup (required for dual-write)

1. Install PostgreSQL 16 from <https://www.postgresql.org/download/windows/>.
2. During install:
   - Keep default port `5432`.
   - Set a password for the `postgres` superuser.
3. Open **SQL Shell (psql)** and run:

```sql
create user brandrank_app with password 'brandrank_dev_pw';
create database brandrank_poc owner brandrank_app;
grant all privileges on database brandrank_poc to brandrank_app;
```

4. In repository `.env` add:

```dotenv
BAI_STORAGE_MODE=dual
BAI_POSTGRES_URL=postgresql+psycopg://brandrank_app:brandrank_dev_pw@127.0.0.1:5432/brandrank_poc
```

Check Python:

```powershell
py --version
```

## Create the virtual environment

From the repository root:

```powershell
cd "C:\path\to\brand-activation-intelligence copy"
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Confirm that `(.venv)` appears in the prompt:

```powershell
python --version
where.exe python
```

## Install dependencies

With `(.venv)` active:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the backend smoke tests:

```powershell
python -m pytest -q tests/test_remediation_smoke.py
```

## Configure the runtime

The backend reads the repository-level `.env` file. For a new checkout:

```powershell
cd ..
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
cd backend
```

By default, the application uses project-relative paths:

- Database: `data\working\bai.duckdb`
- Input: `data\input`
- Output: `data\output`

Optional POC context in `.env`:

```dotenv
BAI_BRAND_ID=aveeno
BAI_BRAND_DISPLAY=Aveeno
BAI_MARKET=US
BAI_LANGUAGE=en-US
BAI_SOURCE_SYSTEM=BrandRank
```

Live Azure/OpenAI settings are optional. Without valid credentials, the Assistant uses the deterministic evidence fallback.

## Start FastAPI

From `backend` with `(.venv)` active:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify it from another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected status: `ok`. API documentation: `http://127.0.0.1:8000/docs`.

## Ingest vendor data

Yes—copy the source `.csv` or `.tsv` files into the repository input folder:

```text
data\input\
  VisibilityModule\
    aveeno_search_term_2026-08-07.csv
  AIVulnerabilityModule\
    aveeno_accuracy_statement_2026-08-07.csv
  ContentReadinessModule\
    aveeno_content_readiness_2026-08-07.csv
```

The discovery process scans subfolders recursively. It also reads `.zip` files and CSV/TSV files inside them, including nested ZIPs. Keep the original files unchanged; the filename and module folder help infer context.

Do not place files in `data\working` or `data\output`. Those folders contain generated database and export artifacts.

Trigger ingestion while FastAPI is running:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/ingest
```

The response reports physical files, unique payloads, parsed rows, rejected rows, duplicates, quarantined schemas, and archive entries. Then evaluate the signal rules:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/signals/evaluate
```

Inspect the resulting run and data quality:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/dataset-status
Invoke-RestMethod http://127.0.0.1:8000/api/quality
Invoke-RestMethod http://127.0.0.1:8000/api/ingestion-errors
```

Unsupported non-empty schemas are quarantined rather than silently promoted. Raw rows remain available through Evidence Explorer, while only contract-eligible metrics become canonical governed fields.

## Seed the Golden Demo

The seed is additive and repeatable; it does not reset the database. Simulated rows are labelled `DEMO_FIXTURE`.

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/seed-fixtures
Invoke-RestMethod http://127.0.0.1:8000/api/context/current
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/signals/evaluate
Invoke-RestMethod "http://127.0.0.1:8000/api/evidence?evidence_type=DEMO_FIXTURE&limit=25"
```

For the complete demo flow—seed fixtures, ingest all input files with the password-gated override, show `processed / total` progress, evaluate signals, and print final counts—run this from the repository root while FastAPI is running:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo_ingest.ps1
```

The hardcoded demo override password is:

```text
KENVUE-DEMO-2026
```

The override does not delete the database. It creates a new ingestion run and reprocesses payloads that were already ingested. Normal ingestion without the override is protected from accidentally reprocessing the same input payloads.

## Stop and reuse

Stop FastAPI with `Ctrl+C`. To deactivate Python:

```powershell
deactivate
```

Next time:

```powershell
cd "C:\path\to\brand-activation-intelligence copy\backend"
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Troubleshooting

### `ModuleNotFoundError`

Activate `.venv` and install requirements again:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Port 8000 is busy

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

### DuckDB is locked

Stop other backend, pytest, or Python processes using the database, then restart FastAPI. Do not reset the database for normal startup.

### Stale macOS paths in `.env`

On Windows, stale `/Users/...` path values are ignored and project-relative defaults are used. You may also remove those path overrides or replace them with absolute Windows paths.
