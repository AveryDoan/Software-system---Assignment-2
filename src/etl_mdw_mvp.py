from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass
class ETLCounts:
    dim_patient: int = 0
    dim_time: int = 0
    fact_encounter: int = 0
    fact_lab: int = 0
    dropped_rows: int = 0


def parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def age_band_for_dob(dob: date, as_of: date) -> str | None:
    age = int((as_of - dob).days // 365.25)
    if age < 0 or age > 120:
        return None
    if age <= 17:
        return "0-17"
    if age <= 34:
        return "18-34"
    if age <= 64:
        return "35-64"
    return "65+"


def normalize_sex(value: str) -> str:
    v = (value or "").strip().upper()
    if v in {"M", "F"}:
        return v
    return "U"


def normalize_result_flag(raw_flag: str, result_value: float) -> str:
    cleaned = (raw_flag or "").strip().upper()
    if cleaned in {"LOW", "NORMAL", "HIGH"}:
        return cleaned
    if result_value < 3.0:
        return "LOW"
    if result_value > 7.0:
        return "HIGH"
    return "NORMAL"


def execute_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(schema_sql)


def truncate_tables(conn: sqlite3.Connection) -> None:
    tables = [
        "stg_patients",
        "stg_encounters",
        "stg_lab_results",
        "FactEncounter",
        "FactLabResult",
        "DimPatient",
        "DimTime",
    ]
    for table in tables:
        conn.execute(f"DELETE FROM {table}")


def load_csv_to_staging(conn: sqlite3.Connection, data_dir: Path) -> None:
    file_map = {
        "patients.csv": ("stg_patients", ["PatientID", "Sex", "DOB"]),
        "encounters.csv": (
            "stg_encounters",
            ["EncounterID", "PatientID", "AdmitDate", "DischargeDate"],
        ),
        "lab_results.csv": (
            "stg_lab_results",
            ["LabResultID", "PatientID", "ResultDate", "ResultValue", "ResultFlag"],
        ),
    }

    for filename, (table, columns) in file_map.items():
        csv_path = data_dir / filename
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = [tuple((row.get(col) or "").strip() for col in columns) for row in reader]
            placeholders = ", ".join(["?"] * len(columns))
            conn.executemany(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                rows,
            )


def populate_dim_patient(conn: sqlite3.Connection, counts: ETLCounts, as_of: date) -> None:
    rows = conn.execute(
        "SELECT PatientID, Sex, DOB FROM stg_patients"
    ).fetchall()
    inserted = 0

    for row in rows:
        raw_id, raw_sex, raw_dob = row
        try:
            patient_id = int(raw_id)
        except (TypeError, ValueError):
            counts.dropped_rows += 1
            continue

        dob = parse_date(raw_dob)
        if dob is None:
            counts.dropped_rows += 1
            continue

        age_band = age_band_for_dob(dob, as_of)
        if age_band is None:
            counts.dropped_rows += 1
            continue

        sex = normalize_sex(raw_sex)
        conn.execute(
            "INSERT OR REPLACE INTO DimPatient (PatientID, Sex, AgeBand) VALUES (?, ?, ?)",
            (patient_id, sex, age_band),
        )
        inserted += 1

    counts.dim_patient = inserted


def populate_dim_time(conn: sqlite3.Connection, counts: ETLCounts) -> None:
    date_strings = []

    encounter_dates = conn.execute("SELECT AdmitDate FROM stg_encounters").fetchall()
    lab_dates = conn.execute("SELECT ResultDate FROM stg_lab_results").fetchall()

    for (raw_date,) in encounter_dates + lab_dates:
        dt = parse_date(raw_date)
        if dt is not None:
            date_strings.append(dt)

    unique_dates = sorted(set(date_strings))
    inserted = 0

    for dt in unique_dates:
        time_id = int(dt.strftime("%Y%m%d"))
        conn.execute(
            "INSERT OR REPLACE INTO DimTime (TimeID, Date, Month, Year) VALUES (?, ?, ?, ?)",
            (time_id, dt.isoformat(), dt.month, dt.year),
        )
        inserted += 1

    counts.dim_time = inserted


def populate_fact_encounter(conn: sqlite3.Connection, counts: ETLCounts) -> None:
    rows = conn.execute(
        "SELECT EncounterID, PatientID, AdmitDate, DischargeDate FROM stg_encounters"
    ).fetchall()
    inserted = 0

    for row in rows:
        raw_enc_id, raw_patient_id, raw_admit, raw_discharge = row

        try:
            encounter_id = int(raw_enc_id)
            patient_id = int(raw_patient_id)
        except (TypeError, ValueError):
            counts.dropped_rows += 1
            continue

        admit = parse_date(raw_admit)
        discharge = parse_date(raw_discharge)
        if admit is None or discharge is None:
            counts.dropped_rows += 1
            continue

        if not conn.execute(
            "SELECT 1 FROM DimPatient WHERE PatientID = ?", (patient_id,)
        ).fetchone():
            counts.dropped_rows += 1
            continue

        time_id = int(admit.strftime("%Y%m%d"))
        if not conn.execute("SELECT 1 FROM DimTime WHERE TimeID = ?", (time_id,)).fetchone():
            counts.dropped_rows += 1
            continue

        los = (discharge - admit).days
        if los < 0:
            counts.dropped_rows += 1
            continue

        conn.execute(
            """
            INSERT OR REPLACE INTO FactEncounter (EncounterID, PatientID, TimeID, LengthOfStay)
            VALUES (?, ?, ?, ?)
            """,
            (encounter_id, patient_id, time_id, los),
        )
        inserted += 1

    counts.fact_encounter = inserted


def populate_fact_lab_result(conn: sqlite3.Connection, counts: ETLCounts) -> None:
    rows = conn.execute(
        "SELECT LabResultID, PatientID, ResultDate, ResultValue, ResultFlag FROM stg_lab_results"
    ).fetchall()
    inserted = 0

    for row in rows:
        raw_lab_id, raw_patient_id, raw_date, raw_value, raw_flag = row

        try:
            lab_result_id = int(raw_lab_id)
            patient_id = int(raw_patient_id)
            result_value = float(raw_value)
        except (TypeError, ValueError):
            counts.dropped_rows += 1
            continue

        result_date = parse_date(raw_date)
        if result_date is None:
            counts.dropped_rows += 1
            continue

        if not conn.execute(
            "SELECT 1 FROM DimPatient WHERE PatientID = ?", (patient_id,)
        ).fetchone():
            counts.dropped_rows += 1
            continue

        time_id = int(result_date.strftime("%Y%m%d"))
        if not conn.execute("SELECT 1 FROM DimTime WHERE TimeID = ?", (time_id,)).fetchone():
            counts.dropped_rows += 1
            continue

        result_flag = normalize_result_flag(raw_flag, result_value)
        conn.execute(
            """
            INSERT OR REPLACE INTO FactLabResult (LabResultID, PatientID, TimeID, ResultValue, ResultFlag)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lab_result_id, patient_id, time_id, result_value, result_flag),
        )
        inserted += 1

    counts.fact_lab = inserted


def run_etl(db_path: Path, data_dir: Path, schema_path: Path) -> ETLCounts:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        execute_schema(conn, schema_path)
        truncate_tables(conn)

        started_at = datetime.utcnow().isoformat(timespec="seconds")
        log_cursor = conn.execute(
            "INSERT INTO ETLRunLog (RunStartedAt, Status, Notes) VALUES (?, ?, ?)",
            (started_at, "RUNNING", "MVP demo ETL execution"),
        )
        run_id = log_cursor.lastrowid

        counts = ETLCounts()
        try:
            load_csv_to_staging(conn, data_dir)
            populate_dim_patient(conn, counts, as_of=date.today())
            populate_dim_time(conn, counts)
            populate_fact_encounter(conn, counts)
            populate_fact_lab_result(conn, counts)

            finished_at = datetime.utcnow().isoformat(timespec="seconds")
            conn.execute(
                """
                UPDATE ETLRunLog
                SET RunFinishedAt = ?,
                    Status = ?,
                    RowsDimPatient = ?,
                    RowsDimTime = ?,
                    RowsFactEncounter = ?,
                    RowsFactLabResult = ?,
                    Notes = ?
                WHERE RunID = ?
                """,
                (
                    finished_at,
                    "SUCCESS",
                    counts.dim_patient,
                    counts.dim_time,
                    counts.fact_encounter,
                    counts.fact_lab,
                    f"Dropped rows: {counts.dropped_rows}",
                    run_id,
                ),
            )
            conn.commit()
        except Exception as exc:
            finished_at = datetime.utcnow().isoformat(timespec="seconds")
            conn.execute(
                "UPDATE ETLRunLog SET RunFinishedAt = ?, Status = ?, Notes = ? WHERE RunID = ?",
                (finished_at, "FAILED", str(exc), run_id),
            )
            conn.commit()
            raise

    return counts
