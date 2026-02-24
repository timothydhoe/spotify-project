"""
filename: parse_data.py
------------------
Load FIT files and check-in files.

Returns: DataFrames

"""
import pandas as pd
from pathlib import Path

def load_fit_files(smartwatch_dir: Path) -> pd.DataFrame:
    """
    Load all FIT files from smartwatch directory.
    
    Expected structure: smartwatch_dir/{participant}/*.fit
    Returns: DataFrame with columns [participant_id, timestamp, metric, value]
    """
    # TODO: Implement once FIT files are available
    # Use fitparse library to extract records
    # Return long-format DataFrame
    pass


def load_checkins(checkin_csv: Path) -> pd.DataFrame:
    """
    Load check-in data from Google Forms export.
    
    Expected columns: timestamp, participant_id, playlist_id, tired, neutral, stressed
    Returns: DataFrame with validated check-in events
    """
    # TODO: Load CSV, parse timestamps
    # Return DataFrame with check-in events
    pass