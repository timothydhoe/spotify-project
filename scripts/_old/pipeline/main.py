"""
filename: main.py
------------------
Run the data pipeline
"""

from pathlib import Path
from pipeline_config import (
    BRONZE_SMARTWATCH, BRONZE_CHECKINS,
    SILVER_SMARTWATCH, SILVER_CHECKINS,
    GOLD_EVENTS, WINDOW_BEFORE, WINDOW_AFTER
)
from modules.parse_data import load_fit_files, load_checkins
from modules.clean import clean_smartwatch, clean_checkins
from modules.extract_windows import get_window_for_event

def main():
    """Run the full data pipeline: bronze → silver → gold."""
    
    print("=== PHASE 1: Load data (Bronze) ===")
    # smartwatch_df = load_fit_files(BRONZE_SMARTWATCH)
    # checkins_df = load_checkins(BRONZE_CHECKINS / "responses.csv")
    
    print("=== PHASE 2: Clean data (Silver) ===")
    # smartwatch_clean = clean_smartwatch(smartwatch_df)
    # checkins_clean = clean_checkins(checkins_df)
    
    # Save to silver
    # SILVER_SMARTWATCH.parent.mkdir(parents=True, exist_ok=True)
    # smartwatch_clean.to_csv(SILVER_SMARTWATCH, index=False)
    # checkins_clean.to_csv(SILVER_CHECKINS, index=False)
    
    print("=== PHASE 3: Extract windows (Gold) ===")
    # for idx, checkin_row in checkins_clean.iterrows():
    #     window_df = get_window_for_event(smartwatch_clean, checkin_row, WINDOW_BEFORE, WINDOW_AFTER)
    #     
    #     participant_id = checkin_row['participant_id']
    #     event_id = f"event_{idx:03d}"
    #     
    #     out_dir = GOLD_EVENTS / participant_id
    #     out_dir.mkdir(parents=True, exist_ok=True)
    #     window_df.to_csv(out_dir / f"{event_id}.csv", index=False)
    
    print("Pipeline complete!")

if __name__ == "__main__":
    main()