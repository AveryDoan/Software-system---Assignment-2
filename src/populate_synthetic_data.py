from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"


@dataclass
class Config:
    seed: int = 20260426
    patient_count: int = 320
    encounter_mean: float = 3.8
    encounter_sd: float = 1.4
    los_mean: float = 4.8
    los_sd: float = 2.0
    labs_per_enc_mean: float = 2.6
    labs_per_enc_sd: float = 1.0
    lab_value_mean: float = 5.2
    lab_value_sd: float = 1.7


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def derive_dob_from_age(age_years: int, rng: random.Random, as_of: date) -> date:
    # Subtract age in years plus a random intra-year offset to keep DOB <= as_of.
    years_in_days = age_years * 365
    intra_year_offset = rng.randint(0, 364)
    return as_of - timedelta(days=years_in_days + intra_year_offset)


def result_flag(result_value: float) -> str:
    if result_value < 3.0:
        return "LOW"
    if result_value > 7.0:
        return "HIGH"
    return "NORMAL"


def generate(config: Config) -> None:
    rng = random.Random(config.seed)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    as_of = date.today()

    patients: list[tuple[int, str, str]] = []
    encounters: list[tuple[int, int, str, str]] = []
    labs: list[tuple[int, int, str, float, str]] = []

    patient_id_start = 3001
    encounter_id = 120001
    lab_id = 180001

    for i in range(config.patient_count):
        patient_id = patient_id_start + i

        # Ages are sampled from a normal distribution to mimic real hospital cohorts.
        age = int(round(clamp(rng.gauss(49.0, 23.0), 0, 95)))
        dob = derive_dob_from_age(age, rng, as_of)

        sex_roll = rng.random()
        if sex_roll < 0.49:
            sex = "F"
        elif sex_roll < 0.98:
            sex = "M"
        else:
            sex = "X"

        patients.append((patient_id, sex, dob.isoformat()))

        encounter_count = int(round(clamp(rng.gauss(config.encounter_mean, config.encounter_sd), 1, 8)))
        for _ in range(encounter_count):
            admit_day = rng.randint(1, 365)
            admit = date(2025, 1, 1) + timedelta(days=admit_day - 1)
            los_days = int(round(clamp(rng.gauss(config.los_mean, config.los_sd), 1, 14)))
            discharge = admit + timedelta(days=los_days)

            encounters.append((encounter_id, patient_id, admit.isoformat(), discharge.isoformat()))

            labs_this_enc = int(
                round(clamp(rng.gauss(config.labs_per_enc_mean, config.labs_per_enc_sd), 1, 6))
            )
            for _ in range(labs_this_enc):
                lab_offset = rng.randint(0, max(0, los_days - 1))
                result_date = admit + timedelta(days=lab_offset)
                value = round(clamp(rng.gauss(config.lab_value_mean, config.lab_value_sd), 0.4, 13.0), 2)
                flag = result_flag(value)
                labs.append((lab_id, patient_id, result_date.isoformat(), value, flag))
                lab_id += 1

            encounter_id += 1

    with (RAW_DIR / "patients.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["PatientID", "Sex", "DOB"])
        writer.writerows(patients)

    with (RAW_DIR / "encounters.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["EncounterID", "PatientID", "AdmitDate", "DischargeDate"])
        writer.writerows(encounters)

    with (RAW_DIR / "lab_results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["LabResultID", "PatientID", "ResultDate", "ResultValue", "ResultFlag"])
        writer.writerows(labs)

    print("Synthetic data generated")
    print(f"Patients: {len(patients)}")
    print(f"Encounters: {len(encounters)}")
    print(f"LabResults: {len(labs)}")


if __name__ == "__main__":
    generate(Config())
