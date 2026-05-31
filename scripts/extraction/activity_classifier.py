"""
activity_classifier.py — Stage 1: Classify per-minute smartwatch data into activity states.

States: Sleep | Rest | Light | Medium | Heavy

Design: heuristic thresholds with an sklearn-compatible interface so the classifier can be
swapped for a RandomForestClassifier or HMM without changing downstream code.

Input columns (all optional except heart_rate or stress):
    heart_rate      — bpm
    stress          — Garmin stress score 0–100
    body_battery    — Garmin energy index 0–100
    intensity       — Garmin intensity label from FIT monitoring messages
    activity_type   — Garmin activity type label
    steps_per_min   — step count per minute

Window: 5-minute rolling median applied to numeric signals before classification.
"""

import numpy as np
import pandas as pd

STATES = ["Sleep", "Rest", "Light", "Medium", "Heavy"]
WINDOW_MIN = 5


class ActivityClassifier:
    """Classify per-minute physiological data into 5 activity states.

    Implements fit() / predict() so it can be swapped for an sklearn estimator.
    """

    def __init__(self, window_min: int = WINDOW_MIN):
        self.window_min = window_min

    def fit(self, X: pd.DataFrame, y=None):
        """No-op for the heuristic classifier. Reserved for ML subclass."""
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Classify each row into an activity state.

        Args:
            X: DataFrame indexed by timestamp with any subset of supported columns.

        Returns:
            Series of state labels aligned to X's index.
        """
        df = _smooth(X, self.window_min)
        return df.apply(_classify_row, axis=1).rename("activity_state")

    def fit_predict(self, X: pd.DataFrame, y=None) -> pd.Series:
        return self.fit(X, y).predict(X)


def _smooth(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Apply rolling median to numeric signal columns."""
    out = df.copy()
    for col in ["heart_rate", "stress", "body_battery", "steps_per_min"]:
        if col in out.columns:
            out[col] = out[col].rolling(window, min_periods=1, center=True).median()
    # Body battery derivative: 5-min slope (positive = recovering, negative = draining)
    if "body_battery" in out.columns:
        out["_bb_slope"] = out["body_battery"].diff(window).fillna(0)
    else:
        out["_bb_slope"] = 0.0
    return out


def _classify_row(row: pd.Series) -> str | None:
    """Apply heuristic rules to a single (smoothed) row.

    Returns None when no data is available (no-wear gap) so that downstream
    code can distinguish 'unknown' from any classified state.
    """
    hr = row.get("heart_rate", np.nan)
    stress = row.get("stress", np.nan)
    bb_slope = row.get("_bb_slope", 0.0)
    steps = row.get("steps_per_min", 0.0) or 0.0
    hour = row.name.hour if hasattr(row.name, "hour") else 12

    hr = float(hr) if pd.notna(hr) else np.nan
    stress = float(stress) if pd.notna(stress) else np.nan

    # No-wear gap: both primary signals absent → unknown, do not classify
    if np.isnan(hr) and np.isnan(stress):
        return None

    # ── Overnight presumption (22:00–08:00) ─────────────────────────────────
    # Default to Sleep unless the watch sees clear signs of wakefulness.
    # This handles REM sleep (HR 75–90 bpm) and daytime-nap periods correctly.
    # Explicit wake signals: steps detected OR HR clearly elevated (> 95 bpm).
    is_overnight = hour >= 22 or hour < 8
    if is_overnight:
        clearly_awake = steps > 0 or (not np.isnan(hr) and hr > 95)
        if not clearly_awake:
            return "Sleep"

    # ── Prefer Garmin's own intensity label when available ───────────────────
    intensity = row.get("intensity") if hasattr(row, "get") else None
    if pd.notna(intensity) and intensity not in ("", None):
        garmin_state = _map_garmin_intensity(str(intensity), row)
        if garmin_state:
            return garmin_state

    # ── Daytime heuristics ───────────────────────────────────────────────────
    # Heavy: very elevated HR or high stress + draining BB
    if (not np.isnan(hr) and hr > 130) or (not np.isnan(stress) and stress > 70 and bb_slope < -1):
        return "Heavy"

    # Medium: elevated HR or moderate stress
    if (not np.isnan(hr) and hr > 100) or (not np.isnan(stress) and stress > 50):
        return "Medium"

    # Light: mildly elevated HR or steps detected
    if (not np.isnan(hr) and hr > 78) or steps > 5:
        return "Light"

    return "Rest"


def _map_garmin_intensity(intensity: str, row: pd.Series) -> str | None:
    """Map Garmin intensity label to a state, using HR as tie-breaker."""
    hr = float(row.get("heart_rate", np.nan)) if pd.notna(row.get("heart_rate")) else np.nan
    hour = row.name.hour if hasattr(row.name, "hour") else 12

    if intensity == "sedentary":
        if (hour >= 22 or hour < 8) and (np.isnan(hr) or hr < 65):
            return "Sleep"
        return "Rest"
    if intensity == "rest":
        return "Rest"
    if intensity == "light":
        return "Light"
    if intensity == "active":
        return "Medium" if (np.isnan(hr) or hr <= 120) else "Heavy"
    if intensity == "highly_active":
        return "Heavy"
    return None
