PRAGMA foreign_keys = ON;

-- Staging tables
CREATE TABLE IF NOT EXISTS stg_patients (
    PatientID TEXT,
    Sex TEXT,
    DOB TEXT
);

CREATE TABLE IF NOT EXISTS stg_encounters (
    EncounterID TEXT,
    PatientID TEXT,
    AdmitDate TEXT,
    DischargeDate TEXT
);

CREATE TABLE IF NOT EXISTS stg_lab_results (
    LabResultID TEXT,
    PatientID TEXT,
    ResultDate TEXT,
    ResultValue TEXT,
    ResultFlag TEXT
);

-- Dimension tables
CREATE TABLE IF NOT EXISTS DimPatient (
    PatientID INTEGER PRIMARY KEY,
    Sex TEXT NOT NULL,
    AgeBand TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS DimTime (
    TimeID INTEGER PRIMARY KEY,
    Date TEXT NOT NULL UNIQUE,
    Month INTEGER NOT NULL,
    Year INTEGER NOT NULL
);

-- Fact tables
CREATE TABLE IF NOT EXISTS FactEncounter (
    EncounterID INTEGER PRIMARY KEY,
    PatientID INTEGER NOT NULL,
    TimeID INTEGER NOT NULL,
    LengthOfStay INTEGER NOT NULL,
    FOREIGN KEY (PatientID) REFERENCES DimPatient(PatientID),
    FOREIGN KEY (TimeID) REFERENCES DimTime(TimeID)
);

CREATE TABLE IF NOT EXISTS FactLabResult (
    LabResultID INTEGER PRIMARY KEY,
    PatientID INTEGER NOT NULL,
    TimeID INTEGER NOT NULL,
    ResultValue REAL NOT NULL,
    ResultFlag TEXT NOT NULL CHECK (ResultFlag IN ('LOW', 'NORMAL', 'HIGH')),
    FOREIGN KEY (PatientID) REFERENCES DimPatient(PatientID),
    FOREIGN KEY (TimeID) REFERENCES DimTime(TimeID)
);

-- ETL run monitoring
CREATE TABLE IF NOT EXISTS ETLRunLog (
    RunID INTEGER PRIMARY KEY AUTOINCREMENT,
    RunStartedAt TEXT NOT NULL,
    RunFinishedAt TEXT,
    Status TEXT NOT NULL,
    RowsDimPatient INTEGER DEFAULT 0,
    RowsDimTime INTEGER DEFAULT 0,
    RowsFactEncounter INTEGER DEFAULT 0,
    RowsFactLabResult INTEGER DEFAULT 0,
    Notes TEXT
);
