# Medical Data Warehouse (MDW) - MVP Demo

This repository contains a **demo-only** implementation of a Medical Data Warehouse (MDW) MVP for coursework.

## What this demo includes

- Synthetic CSV data simulating a single hospital EHR extract:
  - `data/raw/patients.csv`
  - `data/raw/encounters.csv`
  - `data/raw/lab_results.csv`
- Basic ETL pipeline in Python:
  - Loads raw CSV into staging tables
  - Cleans/transforms selected fields
  - Populates a star schema in SQLite
- Star schema tables:
  - `DimPatient`
  - `DimTime`
  - `FactEncounter`
  - `FactLabResult`
- Demo analytics queries:
  - Encounters by month (last year)
  - Average length of stay by age band
  - Lab result flag distribution by month

## Project structure

- `src/etl_mdw_mvp.py` - ETL logic and schema creation
- `src/web_app.py` - Flask dashboard and API routes
- `sql/schema.sql` - Warehouse and staging schema
- `sql/demo_queries.sql` - Demo SQL queries
- `data/raw/*.csv` - Synthetic source data
- `warehouse/mdw_mvp.db` - Generated SQLite database after running ETL or the web app

## Run the demo

Use the web application for the demo flow.

## Run the web application

Install dependencies from the repository root:

```bash
python3 -m pip install -r requirements.txt
```

Start the dashboard:

```bash
python3 src/web_app.py
```

Then open:

`http://127.0.0.1:5055`

The web app includes:

- A summary view of warehouse row counts.
- Chart visualizations for:
  - Encounters by month.
  - Average length of stay by age band.
  - Lab result flag distribution by month.
- A rebuild button to rerun ETL from the synthetic CSV data.

## Notes

- This implementation is intentionally simplified for demonstration.
- It does **not** include production security, compliance, real-time ingestion, or multi-hospital integration.
- Use synthetic data only.
