# european-air-cargo-control-tower
End-to-end ETL pipeline and Tableau dashboard tracking live European air cargo flights via the OpenSky Network REST API.
---
## 📌 Executive Summary & Objective
This project implements an end-to-end data pipeline to ingest, clean, store, and analyze real-time air cargo telemetry across major European air corridors using live ADS-B data from the OpenSky Network API.

* **Target Audience:** Supply Chain Analysts, Logistics Operations Managers, and Aviation Data Engineers.
* **Core Challenge:** The OpenSky Network REST API returns all active air traffic without flight-type tags. Freighter flights are isolated by filtering callsign prefixes against a dimension table of major global cargo carriers (e.g., `CLX`, `GEC`, `BOX`, `DHK`, `BCS`, `UPS`, `FDX`).

---

## 🛠️ Tech Stack & Tools
* **Language & ETL:** Python 3 (`requests`, `pandas`, `sqlite3`)
* **Database Management:** SQLite & DB Browser for SQLite
* **Data Visualization:** Tableau Desktop / Tableau Public
* **Data Source:** OpenSky Network REST API (Live State Vectors)

---

## 📐 Pipeline Architecture

1. **Ingestion (Python):** Polling the OpenSky REST API over defined geographical bounding boxes covering key Central European air hubs (FRA, LEJ, LGG).
2. **Transformation & Cleaning:** Normalizing JSON payloads, parsing UNIX timestamps to UTC, handling missing velocity/altitude attributes, and flagging ground vs. airborne states.
3. **Storage (SQLite):** Storing data in a relational schema using primary keys (`icao24` + `time_position`) to prevent duplicate records during API polling.
4. **Analytics & Validation (SQL):** Executing analytical queries in SQLite to compute carrier metrics, velocity distributions, and hub density.
5. **Visualization (Tableau):** Building interactive dashboards mapping flight paths, active fleet counts, and speed profiles.

---

## 🔍 Key SQL Queries & Analytics

### 1. Active Fleet & Position Volume by Carrier
```sql
SELECT 
    c.carrier_name,
    c.callsign_prefix,
    COUNT(f.icao24) AS total_position_pings,
    COUNT(DISTINCT f.icao24) AS unique_aircraft_count
FROM fact_flights f
JOIN dim_carriers c ON f.callsign_prefix = c.callsign_prefix
GROUP BY c.carrier_name, c.callsign_prefix
ORDER BY total_position_pings DESC;

2. Airborne Cruise Profile (Speed & Altitude)

SELECT 
    c.carrier_name,
    f.callsign_prefix,
    ROUND(AVG(f.velocity), 1) AS avg_velocity_mps,
    ROUND(AVG(f.baro_altitude), 1) AS avg_altitude_m,
    COUNT(DISTINCT f.icao24) AS active_airborne_fleet
FROM fact_flights f
JOIN dim_carriers c ON f.callsign_prefix = c.callsign_prefix
WHERE f.on_ground = 0
GROUP BY c.carrier_name, f.callsign_prefix
ORDER BY avg_velocity_mps DESC;

3. Telemetry Market Share (%)
SELECT 
    c.carrier_name,
    c.callsign_prefix,
    COUNT(f.icao24) AS total_position_pings,
    ROUND(COUNT(f.icao24) * 100.0 / SUM(COUNT(f.icao24)) OVER(), 2) AS share_percentage
FROM fact_flights f
JOIN dim_carriers c ON f.callsign_prefix = c.callsign_prefix
GROUP BY c.carrier_name, c.callsign_prefix
ORDER BY share_percentage DESC;

4. Hub Sector Operations (FRA, LEJ, LGG)
SELECT 
    CASE 
        WHEN f.latitude BETWEEN 49.5 AND 50.5 AND f.longitude BETWEEN 8.0 AND 9.0 THEN 'Frankfurt (FRA)'
        WHEN f.latitude BETWEEN 51.0 AND 51.8 AND f.longitude BETWEEN 12.0 AND 12.8 THEN 'Leipzig/Halle (LEJ)'
        WHEN f.latitude BETWEEN 50.3 AND 51.0 AND f.longitude BETWEEN 5.0 AND 5.8 THEN 'Liège (LGG)'
        ELSE 'In-Transit / En-Route'
    END AS cargo_hub,
    COUNT(DISTINCT f.callsign) AS active_flights,
    COUNT(f.icao24) AS total_position_pings,
    SUM(CASE WHEN f.on_ground = 1 THEN 1 ELSE 0 END) AS ground_operations
FROM fact_flights f
GROUP BY cargo_hub
ORDER BY total_position_pings DESC;

📊 Tableau Interactive Dashboard
https://public.tableau.com/views/EuropeanAirCargoTrackingPipelineAnalytics/Dashboard1?:language=en-GB&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link
