from pathlib import Path

# Project structure
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# PATHS
BRONZE = DATA_DIR / "bronze"
SILVER = DATA_DIR / "silver"
GOLD = DATA_DIR / "gold"

BRONZE_SMARTWATCH = BRONZE / "smartwatch"
BRONZE_CHECKINS = BRONZE / "checkins"

SILVER_SMARTWATCH = SILVER / "smartwatch_cleaned.csv"
SILVER_CHECKINS = SILVER / "checkins_validated.csv"

GOLD_EVENTS = GOLD / "event_windows"

# Participants
PARTICIPANTS = ["bosbes", "citroen", "kiwi", "kokosnoot", "limoen", "peer", "watermeloen"]

# Window parameters (in hours)
WINDOW_BEFORE = 1
WINDOW_AFTER = 1