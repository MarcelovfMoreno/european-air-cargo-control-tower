"""
Continuous Ingestion Loop (Polling) for Live Air Cargo Pipeline.

Runs run_once() from fetch_and_store at specified time intervals.
Press Ctrl+C in the terminal to gracefully stop the loop.
"""

import time
from datetime import datetime, timezone
from fetch_and_store import run_once

POLL_INTERVAL_SECONDS = 60

def start_polling():
    print(f"=== Starting Continuous Ingestion Pipeline (Interval: {POLL_INTERVAL_SECONDS}s) ===")
    print("Press CTRL + C in the terminal to stop execution at any time.\n")
    
    cycle_count = 0

    while True:
        try:
            cycle_count += 1
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"--- Cycle #{cycle_count} | {now_utc} ---")
            
            run_once()
            
            print(f"Waiting {POLL_INTERVAL_SECONDS} seconds until next fetch...\n")
            time.sleep(POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n[!] Loop interrupted by user (CTRL+C). Safely shutting down pipeline.")
            break
        except Exception as e:
            print(f"\n[ERROR] Failure occurred in cycle #{cycle_count}: {e}")
            print(f"Waiting {POLL_INTERVAL_SECONDS} seconds before retrying...\n")
            time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    start_polling()