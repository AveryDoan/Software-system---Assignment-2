from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template

try:
    from etl_mdw_mvp import run_etl
except ModuleNotFoundError:
    from src.etl_mdw_mvp import run_etl


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "warehouse" / "mdw_mvp.db"
DATA_DIR = REPO_ROOT / "data" / "raw"
SCHEMA_PATH = REPO_ROOT / "sql" / "schema.sql"


app = Flask(
    __name__,
    template_folder=str(REPO_ROOT / "templates"),
    static_folder=str(REPO_ROOT / "static"),
)


def ensure_warehouse() -> None:
    # Build the demo warehouse on first run so the web dashboard is ready.
    if not DB_PATH.exists():
        run_etl(DB_PATH, DATA_DIR, SCHEMA_PATH)


def fetch_rows(sql: str) -> list[dict[str, object]]:
    ensure_warehouse()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


@app.get("/")
def index() -> str:
    ensure_warehouse()
    summary_sql = """
    SELECT
        (SELECT COUNT(*) FROM DimPatient) AS Patients,
        (SELECT COUNT(*) FROM FactEncounter) AS Encounters,
        (SELECT COUNT(*) FROM FactLabResult) AS LabResults,
        (SELECT COUNT(*) FROM DimTime) AS TimeRows
    """
    summary = fetch_rows(summary_sql)[0]
    return render_template("index.html", summary=summary)


@app.get("/api/encounters-by-month")
def encounters_by_month() -> object:
    sql = """
    SELECT
        t.Year,
        t.Month,
        COUNT(*) AS EncounterCount
    FROM FactEncounter fe
    JOIN DimTime t ON fe.TimeID = t.TimeID
    WHERE t.Year = (
        SELECT MAX(t2.Year)
        FROM FactEncounter fe2
        JOIN DimTime t2 ON fe2.TimeID = t2.TimeID
    )
    GROUP BY t.Year, t.Month
    ORDER BY t.Year, t.Month
    """
    return jsonify(fetch_rows(sql))


@app.get("/api/avg-los-by-age-band")
def avg_los_by_age_band() -> object:
    sql = """
    SELECT
        p.AgeBand,
        ROUND(AVG(fe.LengthOfStay), 2) AS AvgLengthOfStay
    FROM FactEncounter fe
    JOIN DimPatient p ON fe.PatientID = p.PatientID
    GROUP BY p.AgeBand
    ORDER BY CASE p.AgeBand
        WHEN '0-17' THEN 1
        WHEN '18-34' THEN 2
        WHEN '35-64' THEN 3
        WHEN '65+' THEN 4
        ELSE 5
    END
    """
    return jsonify(fetch_rows(sql))


@app.get("/api/lab-flags-by-month")
def lab_flags_by_month() -> object:
    sql = """
    SELECT
        t.Year,
        t.Month,
        flr.ResultFlag,
        COUNT(*) AS ResultCount
    FROM FactLabResult flr
    JOIN DimTime t ON flr.TimeID = t.TimeID
    GROUP BY t.Year, t.Month, flr.ResultFlag
    ORDER BY t.Year, t.Month, flr.ResultFlag
    """
    return jsonify(fetch_rows(sql))


@app.post("/api/rebuild")
def rebuild() -> object:
    counts = run_etl(DB_PATH, DATA_DIR, SCHEMA_PATH)
    return jsonify(
        {
            "status": "ok",
            "counts": {
                "DimPatient": counts.dim_patient,
                "DimTime": counts.dim_time,
                "FactEncounter": counts.fact_encounter,
                "FactLabResult": counts.fact_lab,
                "DroppedRows": counts.dropped_rows,
            },
        }
    )


if __name__ == "__main__":
    ensure_warehouse()
    app.run(host="127.0.0.1", port=5055, debug=True)
