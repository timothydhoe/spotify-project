"""
fit_extractor.py — Extract additional per-minute signals from Garmin FIT monitoring messages.

Complements garmin_pipeline.py extraction (which captures HR, stress, body battery).
This module additionally extracts activity_type, intensity, step count, and calories
from the same monitoring messages.

Called by garmin_pipeline.run() — not a standalone script.

Output columns: intensity, activity_type, steps_per_min, calories_per_min
"""

import sys
from pathlib import Path

# Allow import from the extraction package when called directly or from other scripts
sys.path.insert(0, str(Path(__file__).parent))

import tempfile
import zipfile

import pandas as pd

from utils import reconstruct_timestamp_16


# Garmin FIT intensity enum values
_INTENSITY_MAP = {0: "active", 1: "rest", 2: "activity_detected", 3: "highly_active", 4: "sedentary", 5: "light"}

# Garmin FIT activity_type enum values
_ACTIVITY_MAP = {
    0: "generic", 1: "running", 2: "cycling", 3: "transition",
    4: "fitness_equipment", 5: "swimming", 6: "walking", 7: "sedentary",
    254: "unknown",
}

# current_activity_type_intensity encoding: bits 0–4 = activity_type, bits 5–7 = intensity
_ACTIVITY_MASK = 0b00011111
_INTENSITY_SHIFT = 5


def extract_monitoring_activity(fit_zips: list[Path], date_range: tuple = None) -> pd.DataFrame:
    """Extract per-minute activity signals from FIT monitoring messages.

    Args:
        fit_zips: List of paths to Garmin FIT zip archives.
        date_range: Optional (start, end) datetime tuple to skip out-of-range files.

    Returns:
        DataFrame indexed by UTC timestamp with columns:
        intensity, activity_type, steps_per_min, calories_per_min
    """
    try:
        import fitparse
    except ImportError:
        raise ImportError("fitparse is required: pip install fitparse")

    rows = []

    with tempfile.TemporaryDirectory() as tmpdir:
        fit_paths = []
        for zp in fit_zips:
            try:
                with zipfile.ZipFile(zp) as z:
                    for name in z.namelist():
                        if name.endswith(".fit"):
                            z.extract(name, tmpdir)
                            fit_paths.append(Path(tmpdir) / name)
            except Exception:
                pass

        for fp in fit_paths:
            try:
                base_ts = None
                prev_cycles = None
                prev_ts = None

                for msg in fitparse.FitFile(str(fp)).get_messages():
                    f = {field.name: field.value for field in msg.fields}

                    if msg.name == "monitoring_info":
                        base_ts = f.get("timestamp")
                        prev_cycles = None
                        prev_ts = None
                        continue

                    if msg.name != "monitoring":
                        continue

                    # Reconstruct timestamp (16-bit relative or direct)
                    ts = f.get("timestamp")
                    if not ts and f.get("timestamp_16") and base_ts:
                        ts = reconstruct_timestamp_16(base_ts, f["timestamp_16"])
                    if not ts:
                        continue

                    if date_range and (ts < date_range[0] or ts > date_range[1]):
                        continue

                    # Decode activity_type and intensity
                    activity_type = None
                    intensity = None
                    combined = f.get("current_activity_type_intensity")
                    if combined is not None:
                        try:
                            val = int(combined)
                            activity_type = _ACTIVITY_MAP.get(val & _ACTIVITY_MASK, str(val & _ACTIVITY_MASK))
                            intensity = _INTENSITY_MAP.get(val >> _INTENSITY_SHIFT, str(val >> _INTENSITY_SHIFT))
                        except (ValueError, TypeError):
                            pass
                    else:
                        raw_at = f.get("activity_type")
                        raw_in = f.get("intensity")
                        if raw_at is not None:
                            # fitparse may return an already-decoded string or a raw integer
                            activity_type = (
                                _ACTIVITY_MAP.get(raw_at, str(raw_at))
                                if isinstance(raw_at, int)
                                else str(raw_at)
                            )
                        if raw_in is not None:
                            intensity = (
                                _INTENSITY_MAP.get(raw_in, str(raw_in))
                                if isinstance(raw_in, int)
                                else str(raw_in)
                            )

                    # Steps: differentiate cumulative cycles to get per-minute count
                    raw_cycles = f.get("cycles")
                    steps_per_min = None
                    if raw_cycles is not None:
                        try:
                            cycles = float(raw_cycles)
                            if prev_cycles is not None and prev_ts is not None:
                                dt_min = (ts - prev_ts).total_seconds() / 60
                                if 0 < dt_min <= 5:
                                    delta_cycles = cycles - prev_cycles
                                    if delta_cycles >= 0:
                                        steps_per_min = round(delta_cycles / dt_min, 1)
                            prev_cycles = cycles
                            prev_ts = ts
                        except (ValueError, TypeError):
                            pass

                    # Calories
                    raw_cal = f.get("active_calories") or f.get("calories")
                    calories_per_min = None
                    if raw_cal is not None:
                        try:
                            calories_per_min = float(raw_cal)
                        except (ValueError, TypeError):
                            pass

                    if activity_type is not None or intensity is not None:
                        rows.append({
                            "timestamp":        ts,
                            "intensity":        intensity,
                            "activity_type":    activity_type,
                            "steps_per_min":    steps_per_min,
                            "calories_per_min": calories_per_min,
                        })

            except Exception:
                pass

    if not rows:
        return pd.DataFrame(columns=["intensity", "activity_type", "steps_per_min", "calories_per_min"])

    df = (pd.DataFrame(rows)
          .drop_duplicates("timestamp")
          .sort_values("timestamp")
          .set_index("timestamp"))

    print(f"  Activity: {len(df)} monitoring records extracted from {len(fit_zips)} zip(s)")
    return df
