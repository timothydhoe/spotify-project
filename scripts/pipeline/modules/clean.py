"""
filename: clean.py
------------------
Remove bad data and handles data gaps.

"""

import pandas as pd

def clean_smartwatch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Basic cleaning: drop rows with missing timestamps.
    
    Args:
        df: Raw smartwatch DataFrame
    Returns: Cleaned DataFrame
    """
    # TODO: Drop rows where timestamp is null
    # Later: add outlier detection, gap handling
    pass


def clean_checkins(df: pd.DataFrame) -> pd.DataFrame:
    """
    Basic cleaning: drop incomplete check-in rows.
    
    Args:
        df: Raw check-ins DataFrame
    Returns: Cleaned DataFrame
    """
    # TODO: Drop rows with missing participant_id, timestamp, or playlist_id
    pass