"""
baselines.py — Stage 2: Per-person physiological baselines and recovery curve modeling.

For each participant, computes:
- State-level baseline statistics (HR, stress, BB) per activity state and hour-of-day
- Exponential recovery curves: how fast signals return to baseline after activity transitions
- Recovery time constants (τ) and time-to-90%-recovery per (prior_state, signal) pair

Uses non-session days only (same exclusion logic as cross_participant_analysis.ipynb).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning

from .utils import filter_non_session_days


# Minimum consecutive minutes needed after a transition to attempt a curve fit
_MIN_RECOVERY_POINTS = 10
# Maximum minutes to consider as a "recovery window" after a transition
_RECOVERY_WINDOW_MIN = 90
# Minimum consecutive minutes the participant must have stayed in the higher state
# before we count a downward transition (prevents noise spikes from triggering fits)
_MIN_STATE_STAY_MIN = 3


@dataclass
class RecoveryCurve:
    """Exponential decay parameters for one (state, signal) pair."""
    from_state: str
    signal: str
    tau: float          # time constant in minutes (smaller = faster recovery)
    asymptote: float    # expected resting value
    t_90: float         # minutes to reach 90% of full recovery
    n_obs: int          # number of transition events used to fit
    r_squared: float    # goodness of fit (0–1)

    def predict(self, t: np.ndarray, start_value: float) -> np.ndarray:
        """Predict signal trajectory from t=0 (transition point) onward."""
        return self.asymptote + (start_value - self.asymptote) * np.exp(-t / self.tau)


@dataclass
class PersonBaseline:
    """Per-participant physiological baselines and recovery curves.

    Usage:
        baseline = PersonBaseline()
        baseline.fit(minute_df, session_dates)
        curve = baseline.get_recovery_curve("Heavy", "stress")
        stats = baseline.get_baseline("Rest", hour_of_day=14)
    """

    participant: str = ""
    _state_baselines: dict = field(default_factory=dict)      # {(state, hour): {signal: (mean, std)}}
    _recovery_curves: dict = field(default_factory=dict)      # {(state, signal): RecoveryCurve}
    _state_global_baselines: dict = field(default_factory=dict)  # {state: {signal: (mean, std)}}

    def fit(self, minute_df: pd.DataFrame, session_dates: list[str]) -> "PersonBaseline":
        """Fit baselines and recovery curves on non-session data.

        Args:
            minute_df: Per-minute DataFrame with columns: activity_state, and any of
                       heart_rate, stress, body_battery. Index must be datetime.
            session_dates: List of 'YYYY-MM-DD' strings to exclude from baseline fitting.
        """
        session_date_set = {pd.Timestamp(d).date() for d in session_dates}
        df = filter_non_session_days(minute_df, session_date_set, timestamp_col=None)
        if df.empty:
            warnings.warn(f"[{self.participant}] No non-session data available for baseline fitting")
            return self

        self._fit_state_baselines(df)
        self._fit_recovery_curves(df)
        return self

    def get_baseline(self, state: str, hour_of_day: int | None = None) -> dict:
        """Return mean ± std for each signal in a given state.

        Falls back to global state baseline if no hour-specific data exists.
        """
        if hour_of_day is not None:
            key = (state, hour_of_day)
            if key in self._state_baselines:
                return self._state_baselines[key]
        return self._state_global_baselines.get(state, {})

    def get_recovery_curve(self, from_state: str, signal: str = "stress") -> Optional[RecoveryCurve]:
        """Return the fitted recovery curve for a (prior_state, signal) pair, or None."""
        return self._recovery_curves.get((from_state, signal))

    @classmethod
    def load_from_summary(cls, df: pd.DataFrame, participant: str = "") -> "PersonBaseline":
        """Reconstruct a PersonBaseline from a recovery_baselines.csv DataFrame.

        Only recovery curves are restored (all session_effect.py needs).
        State baselines (get_baseline()) are not available on a loaded instance.

        Args:
            df: DataFrame with columns: from_state, signal, tau_min, asymptote,
                t_90_min, n_obs, r_squared. Typically read from recovery_baselines.csv.
            participant: Optional codename for identification.

        Returns:
            PersonBaseline with _recovery_curves populated.
        """
        instance = cls(participant=participant)
        for _, row in df.iterrows():
            curve = RecoveryCurve(
                from_state=str(row["from_state"]),
                signal=str(row["signal"]),
                tau=float(row["tau_min"]),
                asymptote=float(row["asymptote"]),
                t_90=float(row["t_90_min"]),
                n_obs=int(row["n_obs"]),
                r_squared=float(row["r_squared"]),
            )
            instance._recovery_curves[(curve.from_state, curve.signal)] = curve
        return instance

    def summary(self) -> pd.DataFrame:
        """Return a DataFrame summarising all fitted recovery curves."""
        rows = []
        for (state, sig), curve in self._recovery_curves.items():
            rows.append({
                "from_state": state,
                "signal": sig,
                "tau_min": round(curve.tau, 1),
                "asymptote": round(curve.asymptote, 1),
                "t_90_min": round(curve.t_90, 1),
                "n_obs": curve.n_obs,
                "r_squared": round(curve.r_squared, 3),
            })
        return pd.DataFrame(rows).sort_values(["from_state", "signal"]).reset_index(drop=True)

    # ── Internal fitting methods ─────────────────────────────────────────────

    def _fit_state_baselines(self, df: pd.DataFrame) -> None:
        signals = [c for c in ("heart_rate", "stress", "body_battery") if c in df.columns]
        if "activity_state" not in df.columns:
            return

        for state, group in df.groupby("activity_state"):
            stats = {}
            for sig in signals:
                vals = group[sig].dropna()
                if len(vals) >= 5:
                    stats[sig] = (float(vals.mean()), float(vals.std()))
            self._state_global_baselines[state] = stats

            # Hour-of-day granularity
            if not df.index.dtype == "datetime64[ns]":
                continue
            for hour, hgroup in group.groupby(group.index.hour):
                h_stats = {}
                for sig in signals:
                    vals = hgroup[sig].dropna()
                    if len(vals) >= 3:
                        h_stats[sig] = (float(vals.mean()), float(vals.std()))
                if h_stats:
                    self._state_baselines[(state, hour)] = h_stats

    def _fit_recovery_curves(self, df: pd.DataFrame) -> None:
        if "activity_state" not in df.columns:
            return

        signals = [c for c in ("heart_rate", "stress", "body_battery") if c in df.columns]
        state_order = {"Sleep": 0, "Rest": 1, "Light": 2, "Medium": 3, "Heavy": 4}
        effort = df["activity_state"].map(state_order).fillna(1)

        # Find downward transitions (higher-effort → lower-effort state).
        # Require the participant to have stayed in the higher state for at least
        # _MIN_STATE_STAY_MIN consecutive minutes before counting the transition —
        # this prevents noisy single-minute spikes from generating dozens of useless fits.
        transitions = []
        prev_effort = effort.shift(1)
        transition_mask = effort < prev_effort
        trans_indices = df.index[transition_mask]

        for ts in trans_indices:
            from_state = df.at[ts - pd.Timedelta(minutes=1), "activity_state"] if (
                ts - pd.Timedelta(minutes=1) in df.index) else None
            if from_state is None:
                continue

            # Check that the prior state persisted for at least _MIN_STATE_STAY_MIN minutes
            stay_start = ts - pd.Timedelta(minutes=_MIN_STATE_STAY_MIN)
            prior_window = df.loc[stay_start:ts - pd.Timedelta(minutes=1), "activity_state"]
            if len(prior_window) < _MIN_STATE_STAY_MIN or not (prior_window == from_state).all():
                continue
            window_end = ts + pd.Timedelta(minutes=_RECOVERY_WINDOW_MIN)
            window = df.loc[ts:window_end]
            if len(window) < _MIN_RECOVERY_POINTS:
                continue
            transitions.append((from_state, ts, window))

        # Group by from_state and signal, collect all recovery segments
        segments: dict[tuple, list] = {}
        for from_state, ts, window in transitions:
            for sig in signals:
                series = window[sig].dropna()
                if len(series) >= _MIN_RECOVERY_POINTS:
                    segments.setdefault((from_state, sig), []).append(series)

        for (from_state, sig), all_segments in segments.items():
            baseline_stats = self._state_global_baselines.get("Rest", {}).get(sig)
            if baseline_stats is None:
                baseline_stats = self._state_global_baselines.get("Sleep", {}).get(sig)
            if baseline_stats is None:
                continue
            asymptote = baseline_stats[0]

            # Fit each segment and collect tau estimates
            taus, r2s = [], []
            for seg in all_segments:
                t = np.arange(len(seg), dtype=float)
                y = seg.values.astype(float)
                tau_est = _fit_exp_decay(t, y, asymptote)
                if tau_est is not None:
                    taus.append(tau_est[0])
                    r2s.append(tau_est[1])

            if not taus:
                continue

            tau_median = float(np.median(taus))
            r2_median = float(np.median(r2s))
            t_90 = tau_median * np.log(10)  # time for 90% recovery: t = τ * ln(10)

            self._recovery_curves[(from_state, sig)] = RecoveryCurve(
                from_state=from_state,
                signal=sig,
                tau=tau_median,
                asymptote=asymptote,
                t_90=t_90,
                n_obs=len(taus),
                r_squared=r2_median,
            )


def _fit_exp_decay(t: np.ndarray, y: np.ndarray, asymptote: float) -> Optional[tuple[float, float]]:
    """Fit y = asymptote + (y0 - asymptote) * exp(-t/τ), return (τ, R²) or None."""
    if len(y) < _MIN_RECOVERY_POINTS:
        return None

    y0_est = float(y[0])
    tau_est = float(max(t[-1] / 3, 1.0))

    def model(t, tau):
        return asymptote + (y0_est - asymptote) * np.exp(-t / tau)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            popt, _ = curve_fit(model, t, y, p0=[tau_est], bounds=(0.1, 500), maxfev=2000)
        tau = float(popt[0])
        y_pred = model(t, tau)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        return tau, max(r2, 0.0)
    except (RuntimeError, ValueError):
        return None
