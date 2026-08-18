"""
Step 2 + 3: Fetch live cargo flights from OpenSky, clean/normalize,
and persist into SQLite with correct deduplication.

Requires: credentials.json in the same folder.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone

import requests

DB_PATH = "cargo_tower.db"
API_URL = "https://opensky-network.org/api/states/all"

# European bounding box covering the 15 hubs
BBOX = {
    "lamin": 34.0,
    "lamax": 60.0,
    "lomin": -10.0,
    "lomax": 30.0,
}

# Known cargo-carrier ICAO callsign prefixes -> carrier name
CARGO_CARRIERS = {
    "CLX": "Cargolux",
    "GEC": "Lufthansa Cargo",
    "BOX": "AeroLogic",
    "DHK": "DHL Air",
    "BCS": "EAT Leipzig (DHL)",
    "FDX": "FedEx Express",
    "UPS": "UPS Airlines",
    "ABX": "ABX Air",
}
CARGO_PREFIXES = tuple(CARGO_CARRIERS.keys())

# Global variables for in-memory token caching
_cached_token = None
_token_expires_at = 0


def get_token():
    """Obtains OAuth2 token, reusing valid cached token to avoid auth endpoint rate limits."""
    global _cached_token, _token_expires_at
    current_time = time.time()

    # Reuse token if it exists and has more than 60s remaining before expiration
    if _cached_token and current_time < (_token_expires_at - 60):
        return _cached_token

    # Request new token only if cache is empty or near expiration
    with open("credentials.json") as f:
        creds = json.load(f)

    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": creds["clientId"],
        "client_secret": creds["clientSecret"],
    }
    response = requests.post(token_url, data=payload)
    response.raise_for_status()

    data = response.json()
    _cached_token = data.get("access_token")

    # Store expiration time returned by OpenSky
    expires_in = data.get("expires_in", 1800)
    _token_expires_at = current_time + expires_in

    print("[Auth] New OAuth2 token requested successfully.")
    return _cached_token


def get_db_connection():
    """Create and return a database connection with FK constraints enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn):
    """Create tables if they don't exist yet."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_carriers (
            callsign_prefix TEXT PRIMARY KEY,
            carrier_name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fact_flights (
            icao24 TEXT NOT NULL,
            time_position INTEGER NOT NULL,
            callsign TEXT,
            callsign_prefix TEXT,
            longitude REAL,
            latitude REAL,
            baro_altitude REAL,
            velocity REAL,
            on_ground INTEGER,
            polled_at_utc TEXT NOT NULL,
            PRIMARY KEY (icao24, time_position),
            FOREIGN KEY (callsign_prefix) REFERENCES dim_carriers (callsign_prefix)
        )
    """)
    conn.commit()


def seed_carriers(conn):
    """Populate dim_carriers from the CARGO_CARRIERS lookup."""
    conn.executemany(
        "INSERT OR IGNORE INTO dim_carriers (callsign_prefix, carrier_name) VALUES (?, ?)",
        list(CARGO_CARRIERS.items()),
    )
    conn.commit()


def fetch_states():
    """Call OpenSky /states/all for the bounding box, return raw state vectors."""
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(API_URL, headers=headers, params=BBOX)
    response.raise_for_status()
    data = response.json()
    return data.get("states", []) or []


def filter_cargo(states):
    """Keep only state vectors whose callsign matches a known cargo prefix."""
    cargo = []
    for s in states:
        callsign_raw = s[1]
        if not callsign_raw:
            continue
        callsign = callsign_raw.strip()
        if callsign.startswith(CARGO_PREFIXES):
            cargo.append(s)
    return cargo


def clean_record(state):
    """
    Convert one raw OpenSky state vector into a clean dict ready for SQLite.
    Uses time_position (or last_contact as fallback) to avoid dropping valid flights.
    """
    icao24 = state[0]
    callsign = state[1].strip() if state[1] else None
    time_position = state[3] if state[3] is not None else state[4]
    longitude = state[5]
    latitude = state[6]
    baro_altitude = state[7]
    on_ground = state[8]
    velocity = state[9]

    prefix = next((p for p in CARGO_PREFIXES if callsign and callsign.startswith(p)), None)

    return {
        "icao24": icao24,
        "time_position": time_position,
        "callsign": callsign,
        "callsign_prefix": prefix,
        "longitude": longitude,
        "latitude": latitude,
        "baro_altitude": baro_altitude,
        "velocity": velocity,
        "on_ground": int(on_ground) if on_ground is not None else None,
        "polled_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def store_records(conn, records):
    """
    Insert cleaned records into fact_flights.
    INSERT OR IGNORE handles compound deduplication (icao24 + time_position).
    """
    rows = [
        (
            r["icao24"],
            r["time_position"],
            r["callsign"],
            r["callsign_prefix"],
            r["longitude"],
            r["latitude"],
            r["baro_altitude"],
            r["velocity"],
            r["on_ground"],
            r["polled_at_utc"],
        )
        for r in records
        if r["time_position"] is not None
    ]

    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR IGNORE INTO fact_flights
        (icao24, time_position, callsign, callsign_prefix, longitude, latitude,
         baro_altitude, velocity, on_ground, polled_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    return cursor.rowcount


def run_once():
    """Single fetch-clean-store cycle for the pipeline."""
    with get_db_connection() as conn:
        init_db(conn)
        seed_carriers(conn)

        print("Fetching live states from OpenSky...")
        states = fetch_states()
        print(f"Total flights tracked: {len(states)}")

        cargo_states = filter_cargo(states)
        print(f"Cargo flights identified: {len(cargo_states)}")

        records = [clean_record(s) for s in cargo_states]
        inserted_rows = store_records(conn, records)

        skipped_rows = len(records) - inserted_rows
        print(f"New rows inserted: {inserted_rows} | Duplicates skipped: {skipped_rows}")

        total_rows = conn.execute("SELECT COUNT(*) FROM fact_flights").fetchone()[0]
        print(f"Total rows in fact_flights so far: {total_rows}")


if __name__ == "__main__":
    run_once()