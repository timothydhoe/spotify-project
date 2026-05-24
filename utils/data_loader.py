"""Load all project data at startup. Called once; results cached at module level."""
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
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

    # Combined outputs
    feature_matrix:    pd.DataFrame = field(default_factory=pd.DataFrame)
    recommendations:   dict = field(default_factory=dict)
    significance_tests: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Availability flags
    has_circadian:  dict = field(default_factory=dict)   # p → bool
    has_sessions:   dict = field(default_factory=dict)   # p → bool
    has_traces:     dict = field(default_factory=dict)   # p → bool
    has_features:   dict = field(default_factory=dict)   # p → bool


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

    # combined feature matrix
    d.feature_matrix = _read_csv(DATA / "analysis" / "circadian_baselines" / "feature_matrix.csv")

    # Bayesian recommendations
    rec_path = DATA / "analysis" / "bayesian_recommender" / "recommendations.json"
    if rec_path.exists():
        d.recommendations = json.loads(rec_path.read_text())

    # significance tests
    d.significance_tests = _read_csv(DATA / "analysis" / "circadian_baselines" / "significance_tests.csv")

    # Populate global availability lists
    global PARTICIPANTS_WITH_CIRCADIAN, PARTICIPANTS_WITH_SESSIONS
    global PARTICIPANTS_WITH_TRACES, PARTICIPANTS_WITH_FEATURES
    PARTICIPANTS_WITH_CIRCADIAN = [p for p in PARTICIPANTS if d.has_circadian[p]]
    PARTICIPANTS_WITH_SESSIONS  = [p for p in PARTICIPANTS if d.has_sessions[p]]
    PARTICIPANTS_WITH_TRACES    = [p for p in PARTICIPANTS if d.has_traces[p]]
    PARTICIPANTS_WITH_FEATURES  = [p for p in PARTICIPANTS if d.has_features[p]]

    return d


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


def best_playlist_for(app_data: AppData, participant: str) -> tuple[str, float]:
    """Return (playlist_name, probability) from Bayesian recommendations."""
    recs = app_data.recommendations.get(participant, {})
    if not recs:
        return "Energy", 0.0
    best = max(recs, key=lambda k: recs[k]["mean"])
    prob = recs[best]["mean"]
    total = sum(v["mean"] for v in recs.values())
    pct = round(prob / total * 100) if total > 0 else 0
    return best, pct


# Module-level singleton — loaded once when app.py imports data_loader
APP_DATA: AppData = load_app_data()
