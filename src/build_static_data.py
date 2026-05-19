from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def age_band(age: int) -> str:
    if age <= 17:
        return "0-17"
    if age <= 34:
        return "18-34"
    if age <= 64:
        return "35-64"
    return "65+"


def build(output_dir: Path | str = "static/data") -> None:
    repo = Path(__file__).resolve().parents[1]
    data_dir = repo / "data" / "raw"
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Load sources
    patients = pd.read_csv(data_dir / "patients.csv", parse_dates=["DOB"])
    encounters = pd.read_csv(data_dir / "encounters.csv", parse_dates=["AdmitDate", "DischargeDate"])
    labs = pd.read_csv(data_dir / "lab_results.csv", parse_dates=["ResultDate"])

    # Summary
    summary = {
        "Patients": int(patients.shape[0]),
        "Encounters": int(encounters.shape[0]),
        "LabResults": int(labs.shape[0]),
    }

    # Encounters by month
    encounters["Year"] = encounters["AdmitDate"].dt.year
    encounters["Month"] = encounters["AdmitDate"].dt.month
    ebm = (
        encounters.groupby(["Year", "Month"]) .size().reset_index(name="EncounterCount")
    )
    ebm_records = ebm.sort_values(["Year", "Month"]).to_dict(orient="records")

    # Average LOS by age band
    # compute age at admit date year
    patients = patients.rename(columns={"Sex": "Gender"})
    encounters = encounters.merge(patients[["PatientID", "Gender", "DOB", "Suburb"]], on="PatientID", how="left")
    encounters["LengthOfStay"] = (encounters["DischargeDate"] - encounters["AdmitDate"]).dt.days
    encounters["AgeAtAdmit"] = encounters.apply(lambda r: r["AdmitDate"].year - r["DOB"].year - ((r["AdmitDate"].month, r["AdmitDate"].day) < (r["DOB"].month, r["DOB"].day)), axis=1)
    encounters["AgeBand"] = encounters["AgeAtAdmit"].apply(age_band)
    los = (
        encounters.groupby("AgeBand")["LengthOfStay"].mean().round(2).reset_index(name="AvgLengthOfStay")
    )
    los_records = los.to_dict(orient="records")

    # Lab flags by month
    labs["Year"] = labs["ResultDate"].dt.year
    labs["Month"] = labs["ResultDate"].dt.month
    lfb = (
        labs.groupby(["Year", "Month", "ResultFlag"]).size().reset_index(name="ResultCount")
    )
    lfb_records = lfb.sort_values(["Year", "Month", "ResultFlag"]).to_dict(orient="records")

    # Years
    years = sorted(set(list(ebm["Year"].unique()) + list(labs["Year"].unique())), reverse=True)

    # Suburb list from patients table
    patient_suburbs = sorted(
        [s for s in patients["Suburb"].dropna().astype(str).str.strip().unique().tolist() if s]
    )

    # Patients sample
    patients_sample = patients.head(50).copy()
    # compute age band relative to 2025 as a fallback
    patients_sample["AgeBand"] = patients_sample["DOB"].apply(lambda d: age_band(2025 - d.year))
    patients_sample = patients_sample.rename(columns={"DOB": "DOB_raw"})
    patient_rows = []
    for _, r in patients_sample.iterrows():
        patient_rows.append({
            "PatientID": int(r.PatientID),
            "Gender": r.Gender,
            "AgeBand": r.AgeBand,
            "Suburb": "" if pd.isna(r.Suburb) else str(r.Suburb),
            "Postcode": "",
        })

    # Patients by month (sample list of unique patients seen in each Year-Month)
    pbm = (
        encounters.groupby(["Year", "Month"]) ["PatientID"].unique().reset_index()
    )
    pbm_records: list[dict] = []
    for _, row in pbm.iterrows():
        year = int(row.Year)
        month = int(row.Month)
        pids = list(map(int, row.PatientID.tolist())) if hasattr(row.PatientID, 'tolist') else list(map(int, row.PatientID))
        # join to patients to get Gender/AgeBand
        subset = patients[patients["PatientID"].isin(pids)].copy()
        subset["AgeBand"] = subset["DOB"].apply(lambda d: age_band(2025 - pd.to_datetime(d).year))
        rows = []
        for _, pr in subset.iterrows():
            rows.append({
                "PatientID": int(pr.PatientID),
                "Gender": pr.Gender,
                "AgeBand": pr.AgeBand,
                "Suburb": "" if pd.isna(pr.Suburb) else str(pr.Suburb),
                "Postcode": "",
            })
        pbm_records.append({"Year": year, "Month": month, "Patients": rows})

    # Encounters by suburb (map-friendly aggregate)
    ebs = (
        encounters.groupby(["Suburb"]).size().reset_index(name="EncounterCount")
    )
    ebs = ebs.fillna({"Suburb": "Unknown"})
    ebs_records = ebs.sort_values(["Suburb"]).to_dict(orient="records")

    # Encounters by suburb and month (for time slider / filtering)
    ebsm = (
        encounters.groupby(["Year", "Month", "Suburb"]).size().reset_index(name="EncounterCount")
    )
    ebsm = ebsm.fillna({"Suburb": "Unknown"})
    ebsm_records = ebsm.sort_values(["Year", "Month", "Suburb"]).to_dict(orient="records")

    # Lab flags by suburb
    labs_with_suburb = labs.merge(patients[["PatientID", "Suburb"]], on="PatientID", how="left")
    lfbs = (
        labs_with_suburb.groupby(["Suburb", "ResultFlag"]).size().reset_index(name="ResultCount")
    )
    lfbs = lfbs.fillna({"Suburb": "Unknown"})
    lfbs_records = lfbs.sort_values(["Suburb", "ResultFlag"]).to_dict(orient="records")

    # Lab flags by suburb and month
    lfbsm = (
        labs_with_suburb.groupby(["Year", "Month", "Suburb", "ResultFlag"]).size().reset_index(name="ResultCount")
    )
    lfbsm = lfbsm.fillna({"Suburb": "Unknown"})
    lfbsm_records = lfbsm.sort_values(["Year", "Month", "Suburb", "ResultFlag"]).to_dict(orient="records")

    # Add TimeRows as number of distinct Year/Month combos
    summary["TimeRows"] = int(len(set((ebm["Year"].astype(str) + "-" + ebm["Month"].astype(str)).tolist())))

    # Write outputs
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "encounters_by_month.json").write_text(json.dumps(ebm_records, indent=2))
    (out / "avg_los_by_age_band.json").write_text(json.dumps(los_records, indent=2))
    (out / "lab_flags_by_month.json").write_text(json.dumps(lfb_records, indent=2))
    (out / "years.json").write_text(json.dumps([int(y) for y in years], indent=2))
    (out / "patients_sample.json").write_text(json.dumps(patient_rows, indent=2))
    (out / "patients_by_month.json").write_text(json.dumps(pbm_records, indent=2))
    (out / "encounters_by_suburb.json").write_text(json.dumps(ebs_records, indent=2))
    (out / "encounters_by_suburb_month.json").write_text(json.dumps(ebsm_records, indent=2))
    (out / "lab_flags_by_suburb.json").write_text(json.dumps(lfbs_records, indent=2))
    (out / "lab_flags_by_suburb_month.json").write_text(json.dumps(lfbsm_records, indent=2))
    (out / "patient_suburbs.json").write_text(json.dumps(patient_suburbs, indent=2))

    # Per-patient encounters by month
    pebm = (
        encounters.groupby(["PatientID", "Year", "Month"]).size().reset_index(name="EncounterCount")
    )
    pebm_records = pebm.sort_values(["PatientID", "Year", "Month"]).to_dict(orient="records")
    (out / "patient_encounters_by_month.json").write_text(json.dumps([{k: (int(v) if isinstance(v, (int,)) else v) for k, v in r.items()} for r in pebm_records], indent=2))

    # Per-patient lab flags by month
    plfb = (
        labs.groupby(["PatientID", "Year", "Month", "ResultFlag"]).size().reset_index(name="ResultCount")
    )
    plfb_records = plfb.sort_values(["PatientID", "Year", "Month", "ResultFlag"]).to_dict(orient="records")
    (out / "patient_lab_flags_by_month.json").write_text(json.dumps([{k: (int(v) if isinstance(v, (int,)) else v) for k, v in r.items()} for r in plfb_records], indent=2))


if __name__ == "__main__":
    build()
