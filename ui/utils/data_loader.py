"""Load all project data at startup. Called once; results cached at module level."""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data"

PARTICIPANTS = ["bosbes", "kiwi", "kokosnoot", "limoen", "peer", "watermeloen"]

# Participants with enough data to render each page
PARTICIPANTS_WITH_CIRCADIAN   = []   # populated by load_app_data()
PARTICIPANTS_WITH_SESSIONS    = []
PARTICIPANTS_WITH_TRACES      = []
PARTICIPANTS_WITH_FEATURES    = []


@dataclass
class AppData:
    # Per-participant analysis outputs
    session_features:  dict = field(default_factory=dict)   # p → DataFrame (session_features.csv)
    session_biometrics: dict = field(default_factory=dict)  # p → DataFrame (session_biometrics.csv)
    session_traces:    dict = field(default_factory=dict)   # p → {date_str → DataFrame}
    hourly_baselines:  dict = field(default_factory=dict)   # p → DataFrame (hourly_baseline.csv)
    garmin_minute:     dict = field(default_factory=dict)   # p → DataFrame (timestamp, stress, body_battery, heart_rate)

    # Combined outputs
    feature_matrix:    pd.DataFrame = field(default_factory=pd.DataFrame)
    recommendations:   dict = field(default_factory=dict)
    significance_tests: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Availability flags
    has_circadian:  dict = field(default_factory=dict)   # p → bool
    has_sessions:   dict = field(default_factory=dict)   # p → bool
    has_traces:     dict = field(default_factory=dict)   # p → bool
    has_features:   dict = field(default_factory=dict)   # p → bool

    # Live inference: Ridge model fitted on feature_matrix at startup
    live_model: Any = None            # fitted sklearn Pipeline (imputer + Ridge)
    live_model_cols: list = field(default_factory=list)   # feature column order
    live_imputer_medians: dict = field(default_factory=dict)  # col → median for NaN fill


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def _load_session_traces(participant: str) -> dict[str, pd.DataFrame]:
    trace_dir = DATA / "wearables" / participant / "processed" / "session_traces"
    if not trace_dir.exists():
        return {}
    traces = {}
    for f in sorted(trace_dir.glob("trace_*.csv")):
        df = pd.read_csv(f, parse_dates=["timestamp_utc"])
        # filename: trace_YYYY-MM-DD_playlist.csv
        parts = f.stem.split("_")
        date_str = parts[1]
        traces[date_str] = df
    return traces


def load_app_data() -> AppData:
    d = AppData()

    for p in PARTICIPANTS:
        # hourly baseline (from circadian_baseline.py output)
        hb = _read_csv(DATA / "analysis" / p / "circadian_baselines" / "hourly_baseline.csv")
        d.hourly_baselines[p] = hb
        d.has_circadian[p] = not hb.empty

        # session features (from session_features.csv — older pipeline output)
        sf = _read_csv(DATA / "analysis" / p / "session_features.csv")
        d.session_features[p] = sf
        d.has_features[p] = not sf.empty

        # session biometrics (from wearables pipeline)
        sb = _read_csv(DATA / "wearables" / p / "processed" / "session_biometrics.csv")
        d.session_biometrics[p] = sb
        d.has_sessions[p] = not sb.empty

        # individual session traces
        traces = _load_session_traces(p)
        d.session_traces[p] = traces
        d.has_traces[p] = len(traces) > 0

        # per-minute garmin data for /home wearables timeline
        stress_path = DATA / "wearables" / p / "processed" / "garmin_minute_stress.csv"
        hr_path     = DATA / "wearables" / p / "processed" / "garmin_minute_hr.csv"
        gm_parts = []
        if stress_path.exists():
            gm_parts.append(pd.read_csv(stress_path, parse_dates=["timestamp"]))
        if hr_path.exists():
            hr_df = pd.read_csv(hr_path, parse_dates=["timestamp"])
            gm_parts.append(hr_df)
        if len(gm_parts) == 2:
            gm = pd.merge(gm_parts[0], gm_parts[1], on="timestamp", how="outer")
        elif len(gm_parts) == 1:
            gm = gm_parts[0]
        else:
            gm = pd.DataFrame()
        if not gm.empty:
            gm = gm.sort_values("timestamp").reset_index(drop=True)
        d.garmin_minute[p] = gm

    # combined feature matrix
    d.feature_matrix = _read_csv(DATA / "analysis" / "circadian_baselines" / "feature_matrix.csv")

    # Bayesian recommendations
    rec_path = DATA / "analysis" / "bayesian_recommender" / "recommendations.json"
    if rec_path.exists():
        d.recommendations = json.loads(rec_path.read_text())

    # significance tests
    d.significance_tests = _read_csv(DATA / "analysis" / "circadian_baselines" / "significance_tests.csv")

    # Fit live Ridge model for date-reactive inference on /home
    _fit_live_model(d)

    # Populate global availability lists
    global PARTICIPANTS_WITH_CIRCADIAN, PARTICIPANTS_WITH_SESSIONS
    global PARTICIPANTS_WITH_TRACES, PARTICIPANTS_WITH_FEATURES
    PARTICIPANTS_WITH_CIRCADIAN = [p for p in PARTICIPANTS if d.has_circadian[p]]
    PARTICIPANTS_WITH_SESSIONS  = [p for p in PARTICIPANTS if d.has_sessions[p]]
    PARTICIPANTS_WITH_TRACES    = [p for p in PARTICIPANTS if d.has_traces[p]]
    PARTICIPANTS_WITH_FEATURES  = [p for p in PARTICIPANTS if d.has_features[p]]

    return d


def _fit_live_model(d: AppData) -> None:
    """Fit a Ridge regression on the feature matrix for live per-session inference.

    The model predicts mood_delta from biometric state features. At inference time
    we simulate all three playlist types by swapping the playlist dummy variables,
    then recommend the type with the highest predicted delta.
    """
    fm = d.feature_matrix
    if fm.empty or "mood_delta" not in fm.columns:
        return

    try:
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import Pipeline
    except ImportError:
        return

    fm = fm.dropna(subset=["mood_delta"]).copy()
    if len(fm) < 5:
        return

    # Derived features (same as circadian_ml.py prepare_data)
    fm["hour_sin"]     = np.sin(2 * np.pi * fm["hour_of_day"] / 24)
    fm["hour_cos"]     = np.cos(2 * np.pi * fm["hour_of_day"] / 24)
    fm["dow_sin"]      = np.sin(2 * np.pi * fm["day_of_week"] / 7)
    fm["dow_cos"]      = np.cos(2 * np.pi * fm["day_of_week"] / 7)
    fm["calm_x_dev"]   = fm["playlist_calm"]   * fm["baseline_deviation_entry"]
    fm["energy_x_dev"] = fm["playlist_energy"]  * fm["baseline_deviation_entry"]

    base_cols = [
        "baseline_deviation_entry", "hr_baseline_deviation",
        "playlist_calm", "playlist_energy",
        "mood_before_score", "bb_start", "days_since_last_session",
        "pre_state_encoded", "avg_resp_daily", "session_number",
    ]
    derived_cols = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "calm_x_dev", "energy_x_dev"]

    p_dummies = pd.get_dummies(fm["participant"], prefix="p", drop_first=True)
    all_cols = base_cols + derived_cols + list(p_dummies.columns)

    X = pd.concat([fm[base_cols + derived_cols], p_dummies], axis=1)
    y = fm["mood_delta"]

    # Store imputer medians for NaN-safe inference
    d.live_imputer_medians = {c: float(X[c].median()) if c in X.columns else 0.0 for c in all_cols}

    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", Ridge(alpha=10.0)),
    ])
    pipe.fit(X, y)

    d.live_model = pipe
    d.live_model_cols = all_cols


# Compute hourly expected stress for a participant at a given hour.
# Returns (mean_stress, std_stress) or (None, None) if no baseline.
def expected_stress(app_data: AppData, participant: str, hour: int):
    hb = app_data.hourly_baselines.get(participant, pd.DataFrame())
    if hb.empty or "hour" not in hb.columns:
        return None, None
    row = hb[hb["hour"] == hour]
    if row.empty:
        return None, None
    return float(row["mean_stress"].iloc[0]), float(row["std_stress"].iloc[0])


def best_playlist_for(app_data: AppData, participant: str) -> tuple[str, int]:
    """Return (playlist_name, relative_preference_pct) from Bayesian recommendations.

    relative_preference_pct is this playlist's share of total predicted mood gain
    across all three playlists — NOT a posterior probability.
    Used by /aanbevelingen (historical Bayesian view).
    """
    recs = app_data.recommendations.get(participant, {})
    if not recs:
        return "Neutral", 0  # Neutral is the ISO therapy safe default
    best = max(recs, key=lambda k: recs[k]["mean"])
    best_mean = recs[best]["mean"]
    total = sum(max(v["mean"], 0) for v in recs.values())
    pct = round(best_mean / total * 100) if total > 0 else 0
    return best, pct


def live_recommend(
    app_data: AppData,
    participant: str,
    bio_row: "pd.Series",
) -> tuple[str, dict]:
    """Predict best playlist type from a single session's biometric state.

    Uses the Ridge model fitted at startup on the full feature matrix.
    Simulates all three playlist types by swapping playlist dummy variables.

    Returns (best_playlist_name, {type: predicted_mood_delta}) so callers can
    display confidence context alongside the recommendation.
    Falls back to Bayesian best_playlist_for() if the model is unavailable.
    """
    if app_data.live_model is None or not app_data.live_model_cols:
        pl, _ = best_playlist_for(app_data, participant)
        return pl, {}

    # Build base feature vector from biometric row
    def _safe(col, fallback=0.0):
        v = bio_row.get(col) if hasattr(bio_row, "get") else None
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return app_data.live_imputer_medians.get(col, fallback)
            return float(v)
        except Exception:
            return app_data.live_imputer_medians.get(col, fallback)

    # Extract hour from start_local for cyclical encoding
    hour = 12.0
    start_local = bio_row.get("start_local") if hasattr(bio_row, "get") else None
    if start_local and not (isinstance(start_local, float) and math.isnan(start_local)):
        try:
            hour = float(str(start_local).split(":")[0])
        except Exception:
            pass

    dow = _safe("day_of_week", 3.0)
    baseline_dev = _safe("baseline_deviation_entry")
    session_num = _safe("session_number", 1.0)

    # Participant dummy columns (drop_first removes the alphabetically first participant)
    p_dummies_present = [c for c in app_data.live_model_cols if c.startswith("p_")]

    results = {}
    for playlist_type in ("Calm", "Neutral", "Energy"):
        calm_flag   = 1 if playlist_type == "Calm"   else 0
        energy_flag = 1 if playlist_type == "Energy" else 0

        row_dict: dict = {
            "baseline_deviation_entry":  baseline_dev,
            "hr_baseline_deviation":     _safe("hr_baseline_deviation"),
            "playlist_calm":             calm_flag,
            "playlist_energy":           energy_flag,
            "mood_before_score":         _safe("mood_before_score"),
            "bb_start":                  _safe("bb_start"),
            "days_since_last_session":   _safe("days_since_last_session"),
            "pre_state_encoded":         _safe("pre_state_encoded"),
            "avg_resp_daily":            _safe("avg_resp_daily"),
            "session_number":            session_num,
            "hour_sin":  math.sin(2 * math.pi * hour / 24),
            "hour_cos":  math.cos(2 * math.pi * hour / 24),
            "dow_sin":   math.sin(2 * math.pi * dow / 7),
            "dow_cos":   math.cos(2 * math.pi * dow / 7),
            "calm_x_dev":   calm_flag   * baseline_dev,
            "energy_x_dev": energy_flag * baseline_dev,
        }
        # Participant dummies: set current participant's column to 1, rest to 0
        for col in p_dummies_present:
            p_name = col[len("p_"):]
            row_dict[col] = 1 if participant == p_name else 0

        X_row = pd.DataFrame([row_dict])[app_data.live_model_cols]
        pred = float(app_data.live_model.predict(X_row)[0])
        results[playlist_type] = round(pred, 2)

    best = max(results, key=lambda k: results[k])
    return best, results


_FEATURE_NAMES_NL = {
    "baseline_deviation_entry": "Stressafwijking van basislijn",
    "hr_baseline_deviation":    "HRafwijking van basislijn",
    "playlist_calm":            "Afspeellijst: Kalm",
    "playlist_energy":          "Afspeellijst: Energiek",
    "mood_before_score":        "Stemming voor (score)",
    "bb_start":                 "Body Battery",
    "days_since_last_session":  "Dagen sinds laatste sessie",
    "pre_state_encoded":        "Activiteitsniveau",
    "avg_resp_daily":           "Ademhaling (daggemiddelde)",
    "session_number":           "Sessienummer",
    "hour_sin":                 "Uur (sinus)",
    "hour_cos":                 "Uur (cosinus)",
    "dow_sin":                  "Weekdag (sinus)",
    "dow_cos":                  "Weekdag (cosinus)",
    "calm_x_dev":               "Kalm × stressafwijking",
    "energy_x_dev":             "Energiek × stressafwijking",
}


def explain_live_prediction(
    app_data: AppData,
    participant: str,
    bio_row: "pd.Series",
    playlist_type: str,
) -> list[tuple[str, float]]:
    """Return top-5 Ridge feature attributions (coef × x) for one playlist type.

    For a linear Ridge model, attribution_i = coef_i × x_i gives the
    contribution of each feature to the predicted mood_delta.
    Returns list of (feature_name_nl, attribution) sorted by |attribution|.
    """
    if app_data.live_model is None or not app_data.live_model_cols:
        return []

    def _safe(col, fallback=0.0):
        v = bio_row.get(col) if hasattr(bio_row, "get") else None
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return app_data.live_imputer_medians.get(col, fallback)
            return float(v)
        except Exception:
            return app_data.live_imputer_medians.get(col, fallback)

    hour = 12.0
    start_local = bio_row.get("start_local") if hasattr(bio_row, "get") else None
    if start_local and not (isinstance(start_local, float) and math.isnan(start_local)):
        try:
            hour = float(str(start_local).split(":")[0])
        except Exception:
            pass

    dow = _safe("day_of_week", 3.0)
    baseline_dev = _safe("baseline_deviation_entry")
    calm_flag   = 1 if playlist_type == "Calm"   else 0
    energy_flag = 1 if playlist_type == "Energy" else 0

    p_dummies_present = [c for c in app_data.live_model_cols if c.startswith("p_")]
    row_dict: dict = {
        "baseline_deviation_entry":  baseline_dev,
        "hr_baseline_deviation":     _safe("hr_baseline_deviation"),
        "playlist_calm":             calm_flag,
        "playlist_energy":           energy_flag,
        "mood_before_score":         _safe("mood_before_score"),
        "bb_start":                  _safe("bb_start"),
        "days_since_last_session":   _safe("days_since_last_session"),
        "pre_state_encoded":         _safe("pre_state_encoded"),
        "avg_resp_daily":            _safe("avg_resp_daily"),
        "session_number":            _safe("session_number", 1.0),
        "hour_sin":  math.sin(2 * math.pi * hour / 24),
        "hour_cos":  math.cos(2 * math.pi * hour / 24),
        "dow_sin":   math.sin(2 * math.pi * dow / 7),
        "dow_cos":   math.cos(2 * math.pi * dow / 7),
        "calm_x_dev":   calm_flag   * baseline_dev,
        "energy_x_dev": energy_flag * baseline_dev,
    }
    for col in p_dummies_present:
        p_name = col[len("p_"):]
        row_dict[col] = 1 if participant == p_name else 0

    X_row = pd.DataFrame([row_dict])[app_data.live_model_cols]
    coefs = app_data.live_model["model"].coef_
    x_vals = X_row.values[0]
    attributions = [(col, float(c) * float(x)) for col, c, x in zip(app_data.live_model_cols, coefs, x_vals)]
    # Top 5 by absolute value, exclude near-zero participant dummies
    filtered = [(col, val) for col, val in attributions if not col.startswith("p_")]
    top5 = sorted(filtered, key=lambda kv: abs(kv[1]), reverse=True)[:5]
    return [((_FEATURE_NAMES_NL.get(col, col)), val) for col, val in top5]


# Module-level singleton — loaded once when app.py imports data_loader
APP_DATA: AppData = load_app_data()
