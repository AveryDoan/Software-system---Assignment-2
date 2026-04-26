-- 1) Encounters by month for last year in the dataset
SELECT
    t.Year,
    t.Month,
    COUNT(*) AS EncounterCount
FROM FactEncounter fe
JOIN DimTime t ON fe.TimeID = t.TimeID
WHERE t.Year = (
    SELECT MAX(Year) FROM DimTime
)
GROUP BY t.Year, t.Month
ORDER BY t.Year, t.Month;

-- 2) Average length of stay by age band
SELECT
    p.AgeBand,
    ROUND(AVG(fe.LengthOfStay), 2) AS AvgLengthOfStay
FROM FactEncounter fe
JOIN DimPatient p ON fe.PatientID = p.PatientID
GROUP BY p.AgeBand
ORDER BY
    CASE p.AgeBand
        WHEN '0-17' THEN 1
        WHEN '18-34' THEN 2
        WHEN '35-64' THEN 3
        WHEN '65+' THEN 4
        ELSE 5
    END;

-- 3) Lab result flag distribution by month
SELECT
    t.Year,
    t.Month,
    flr.ResultFlag,
    COUNT(*) AS ResultCount
FROM FactLabResult flr
JOIN DimTime t ON flr.TimeID = t.TimeID
GROUP BY t.Year, t.Month, flr.ResultFlag
ORDER BY t.Year, t.Month, flr.ResultFlag;
