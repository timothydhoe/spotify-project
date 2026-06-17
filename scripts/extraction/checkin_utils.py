"""
checkin_utils.py — Check-in date parsing and auto-correction for Project R.E.M.

Background
----------
The Google Form date field misbehaves on certain mobile clients: the date picker
presents fields in MM-DD-YYYY order instead of DD-MM-YYYY, so participants
accidentally enter month first.  The result is a date where day and month are
swapped (e.g., March 10 becomes "3-10-2026" instead of "10-3-2026").

Detection
---------
The 'Tijdstempel' column is the server-side form submission timestamp and is
always correct.  A check-in date that falls *after* the submission timestamp is
impossible — participants fill in the form during or right after the session,
never before — making it a reliable signal that day and month are swapped.

Correction
----------
When a suspicious date is detected, day and month are swapped in the raw string
and re-parsed.  If the result is on or before the submission date (plus one day
of tolerance for midnight/timezone edge cases), the correction is accepted and a
warning is emitted.  If the swap still does not produce a plausible date, the
original value is kept and a warning is emitted so the researcher can inspect
the row manually.
"""

import re
import warnings
import pandas as pd

CHECKIN_DATE_COL = "Welke dag deed je een check-in?"
TIMESTAMP_COL    = "Tijdstempel"

# How far in the future a check-in date may appear relative to the submission
# timestamp before it is flagged as suspicious.  One day covers midnight
# submissions and minor clock-skew.
_FUTURE_TOLERANCE = pd.Timedelta(days=1)
_PAST_TOLERANCE   = pd.Timedelta(days=7)


def fix_checkin_dates(sessions: pd.DataFrame) -> pd.Series:
    """Return a Series of corrected pd.Timestamps for the check-in date column.

    Applies row-by-row validation: if the parsed check-in date is after the
    submission timestamp, day and month are swapped and the corrected value is
    returned.  A UserWarning is emitted for every row that is auto-corrected or
    that could not be corrected, so problems surface in pipeline output.

    Parameters
    ----------
    sessions : pd.DataFrame
        Must contain at least CHECKIN_DATE_COL ("Welke dag deed je een check-in?")
        and TIMESTAMP_COL ("Tijdstempel").

    Returns
    -------
    pd.Series of timezone-naive pd.Timestamp, one per row.
    """

    def _fix_row(row):
        # Submission timestamp is server-generated in D-M-YYYY format — always correct.
        # Strip trailing timezone abbreviation (EET, EEST, …) before parsing;
        # pandas does not recognise these and will hard-error in a future version.
        ts_clean = re.sub(r"\s+[A-Z]{2,5}$", "", str(row[TIMESTAMP_COL]).strip())
        # Tijdstempel = form-submission time (validation anchor only, not the session date).
        submit_dt = pd.to_datetime(ts_clean, dayfirst=True)
        raw = str(row[CHECKIN_DATE_COL]).strip()
        # Check-in dates are D-M-YYYY as entered in the Google Form.
        checkin_dt = pd.to_datetime(raw, format="%d-%m-%Y")

        # Happy path: date is on or before submission timestamp.
        if submit_dt - _PAST_TOLERANCE <= checkin_dt <= submit_dt + _FUTURE_TOLERANCE:
            return checkin_dt

        # Suspicious: check-in is outside plausible range (>7 days before or >1 day after
        # submission). Try swapping D and M (mobile form bug: MM-DD picker on some devices).
        parts = raw.split("-")
        if len(parts) == 3:
            swapped_raw = f"{parts[1]}-{parts[0]}-{parts[2]}"
            try:
                swapped_dt = pd.to_datetime(swapped_raw, format="%d-%m-%Y")
                if submit_dt - _PAST_TOLERANCE <= swapped_dt <= submit_dt + _FUTURE_TOLERANCE:
                    warnings.warn(
                        f"[check-in date] Submitted {submit_dt.date()}: "
                        f"'{raw}' looks day/month-swapped (mobile bug) — "
                        f"auto-corrected to {swapped_dt.date()}",
                        stacklevel=2,
                    )
                    return swapped_dt
            except ValueError:
                pass

        warnings.warn(
            f"[check-in date] Submitted {submit_dt.date()}: "
            f"date '{raw}' is outside plausible range and could not be auto-corrected — "
            f"please verify this row manually",
            stacklevel=2,
        )
        return checkin_dt

    return sessions.apply(_fix_row, axis=1)
