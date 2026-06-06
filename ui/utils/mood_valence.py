"""Context-aware mood improvement logic for Project R.E.M.

The 1-10 scale measures intensity of the *current* emotion, not a universal
wellbeing scale. Improvement means the composite mood score rose:
    composite = valence × intensity
where valence is -1 for negative emotions (moe, gespannen), 0 for neutral,
and +1 for positive emotions (happy, rustig, gemotiveerd).

This mirrors the same VALENCE_MAP used in scripts/analysis/bayesian_recommender.py.
"""

VALENCE_MAP: dict[str, int] = {
    # Negative (-1)
    "gestresseerd of gespannen": -1,
    "moe of ongemotiveerd":      -1,
    "moe en gespannen...":       -1,
    "moe en gespannen":          -1,
    "gestresseerd":              -1,
    "gespannen":                 -1,
    "moe":                       -1,
    "ongemotiveerd":             -1,
    "verdrietig":                -1,
    "overspannen - geen gevoelens": -1,
    "overspannen":               -1,
    # Neutral (0)
    "neutraal":                  0,
    "neutraal tot een goed gevoel": 0,
    "ok":                        0,
    # Positive (+1)
    "rustig":                    1,
    "gemotiveerd":               1,
    "happy":                     1,
    "happy - gemotiveerd":       1,
    "goed gevoel":               1,
    "relax":                     1,
    "positief":                  1,
    "blij":                      1,
}


def emotion_valence(label: str) -> int:
    """Map a Dutch mood label to its valence (-1, 0, or +1)."""
    key = str(label).strip().lower()
    if key in VALENCE_MAP:
        return VALENCE_MAP[key]
    # Fuzzy fallback
    if any(w in key for w in ("stress", "gespannen", "moe", "ongemot", "verdriet", "overspannen")):
        return -1
    if any(w in key for w in ("happy", "goed", "gemotiv", "rustig", "blij", "relax", "positief")):
        return 1
    return 0


def composite_mood(label: str, score: float) -> float:
    """Return valence-weighted mood composite: valence × intensity.

    Negative emotions yield negative composites, positive yield positive.
    Neutral maps to 0 regardless of intensity.
    """
    try:
        s = float(score)
    except (TypeError, ValueError):
        return 0.0
    return float(emotion_valence(label)) * s


def mood_is_improvement(
    before_label: str,
    before_score,
    after_label: str,
    after_score,
) -> bool | None:
    """Return True if composite mood improved, False if it declined, None if unchanged/unknown.

    Uses composite_mood() so that a negative emotion dropping in intensity
    (e.g. "moe 7 → neutraal 4") correctly registers as improvement.
    """
    try:
        b = float(before_score)
        a = float(after_score)
    except (TypeError, ValueError):
        return None
    import math
    if math.isnan(b) or math.isnan(a):
        return None
    delta = composite_mood(after_label, a) - composite_mood(before_label, b)
    if delta > 0:
        return True
    if delta < 0:
        return False
    return None
