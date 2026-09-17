# Kenvue AEO/GEO Decision Intelligence

An enterprise-grade Decision Intelligence product built for Kenvue leadership. It transforms raw AI observability data into governed, actionable insights.

> **For the optimal presentation flow and script, open [DEMO_HELPER.md](./DEMO_HELPER.md).**

> **For a newcomer-friendly codebase walkthrough tailored to Dhanush's data/BI background, open [docs/DHANUSH_CODEBASE_GUIDE.md](./docs/DHANUSH_CODEBASE_GUIDE.md).**

## Core Architecture

### 1. Semantic Trust Layer (Governance)
We do not trust raw vendor data. Before any signal is analyzed, it passes through the Semantic Trust Layer:
- **Metric Contracts**: Defines what a metric means, its grain, and whether it is verified.
- **Schema Contracts**: Strictly enforces the shape of vendor payloads.
- **Semantic Blockers & Questions**: Halts activation on mathematically incoherent metrics (e.g., misconfigured rank algorithms) and logs them for vendor follow-up.

### 2. Signal Observatory
Signals are not just raw data points; they are deterministic events calculated from Canonical Observations. They are strictly filtered via Governance Tabs (`Verified`, `Experimental`, `Blocked`).

### 3. Governed Activation (Interventions & Outcomes)
Insight without action is useless. The system drafts **Interventions** (e.g., "Rewrite oat science page with semantic markup") that are sent through Medical-Legal-Regulatory (MLR) review. 
Post-publish, the system tracks **Outcomes** with strict attribution limits to measure exact ROI (e.g., visibility delta).

### 4. Leadership Intelligence Assistant
A chat interface that acts as an executive control plane. It is bounded by the **Decision Context Pack**, meaning it can *only* answer using verified, governed evidence. It strictly adheres to a response contract:
- **Headline**: Executive summary.
- **Priorities**: Actionable insights.
- **Evidence**: Specific citations linking back to rows in DuckDB.
- **Limitations**: Transparent warnings if data is insufficient.

## Repository Structure

- `backend/` — FastAPI engine, DuckDB state (`bai.duckdb`), LLM routing, and intelligence logic.
- `frontend/` — Premium React/Vite dashboard built with glassmorphism design tokens.
- `config/` — Domain governance configurations.
- `data/` — Local runtime volumes for data processing.

## Running the Application

For the complete Windows PowerShell backend setup with `venv`, `pip install`, FastAPI startup, smoke tests, and Golden Demo seeding, see [WINDOWS_BACKEND_SETUP.md](./WINDOWS_BACKEND_SETUP.md).

1. **Environment Config**: Copy `.env.example` to `.env` and set `VITE_API_BASE_URL=http://localhost:8000`. Provide your Azure OpenAI keys if you wish to use the live Assistant.
   - For PostgreSQL dual-write, set:
     - `BAI_STORAGE_MODE=dual`
     - `BAI_POSTGRES_URL=postgresql+psycopg://<user>:<password>@127.0.0.1:5432/<database>`
2. **Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
3. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

If opening `http://127.0.0.1:8000` shows `{"detail":"Not Found"}`, that is expected. The API is mounted under `/api`, so use `http://127.0.0.1:8000/api/health` and open docs at `http://127.0.0.1:8000/docs`.

## Start Fresh (Clean Data)
To reset the runtime and clear the DuckDB state:
```bash
bash scripts/clean_data.sh
```

## Scaling to Enterprise
This POC is designed with a strict contract-first architecture:
- **DuckDB + Parquet**: Serves as the canonical data interface, ready to be migrated to Databricks or Snowflake.
- **Frontend API Contracts**: The REST layer is cleanly separated, allowing the React UI to be embedded in broader internal portals or Power BI.
- **Semantic Trust**: Operates as a standalone data governance mesh.
