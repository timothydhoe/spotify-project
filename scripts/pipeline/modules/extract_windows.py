"""
filename: extract_windows.py
------------------
Slice 1 hour before and after listening events.

"""

import pandas as pd
from datetime import timedelta

def get_window_for_event(smartwatch_df: pd.DataFrame, 
                         checkin_row: pd.Series,
                         window_before_hr: int=1,
                         window_after_hr: int=1) -> pd.DataFrame:
    """
    Extract smartwatch data window around a check-in event.
    
    Args:
        smartwatch_df: Cleaned smartwatch data
        checkin_row: Single row from check-ins DataFrame
        window_before_hr: Hours before check-in timestamp
        window_after_hr: Hours after check-in timestamp
    
    Returns: Filtered DataFrame with smartwatch data in time window
    """
    # TODO: Extract participant_id and timestamp from checkin_row
    # TODO: Filter smartwatch_df for this participant
    # TODO: Filter for timestamp between (checkin_time - window_before) and (checkin_time + window_after)
    # TODO: Add metadata columns: event_id, playlist_id, mood scores
    pass