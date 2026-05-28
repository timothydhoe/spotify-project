"""Biometric-state-aware audio feature threshold adjustment for Project R.E.M.

The ISO principle (Thoma et al. 2013) implies that the starting point of a
playlist's BPM/energy arc should match the participant's current arousal level
before gradually guiding them toward the target state.

This module computes adjusted Spotify audio feature thresholds based on
current biometric state (stress, body_battery, activity). The output is used
by the Aanbevelingen page to explain what audio feature profile would best
match the current state — it does NOT regenerate actual playlists.

Scientific rationale:
- High stress + Calm playlist: prefer higher acousticness (warm, analogue
  frequencies are more grounding), lower valence threshold (meet the user
  where they are rather than imposing positivity — ISO matching phase).
- Low body battery + Energy playlist: gentler entrainment helps fatigued
  listeners; raise danceability (rhythmic consistency aids motor entrainment)
  while lowering minimum tempo to 110 so the ascent starts more gently.
- High body battery + Energy playlist: listener can handle a more intense
  energy build; raise minimum tempo to 130 BPM.
"""

from dataclasses import dataclass


@dataclass
class SaltParams:
    """Adjusted audio feature thresholds based on current biometric state."""
    # Calm playlist adjustments
    calm_acousticness_min: float = 0.3
    calm_valence_note: str = ""

    # Energy playlist adjustments
    energy_tempo_min: float = 120.0
    energy_danceability_min: float = 0.5

    # Context note shown to user
    context_notes: list[str] = None

    def __post_init__(self):
        if self.context_notes is None:
            self.context_notes = []


_ACTIVITY_EN = {"Slaap": "Sleep", "Rust": "Rest", "Licht": "Light", "Matig": "Medium", "Zwaar": "Heavy"}


def compute_salt_params(stress: float, body_battery: float, activity: str = "Matig") -> SaltParams:
    """Return ISO-adjusted audio feature thresholds for the given biometric state.

    Parameters
    ----------
    stress : 0-100 Garmin stress score
    body_battery : 0-100 Garmin body battery
    activity : Dutch activity label ("Slaap", "Rust", "Licht", "Matig", "Zwaar")
    """
    params = SaltParams()
    notes = []

    # --- Calm playlist adjustments ---
    if stress > 70:
        params.calm_acousticness_min = 0.5
        params.calm_valence_note = "lagere valence-drempel (ISO-matching: begin bij huidige stemming)"
        notes.append(
            "Kalm: akoestiek-voorkeur verhoogd naar ≥0.5 (rustgevende frequenties bij hoge stress); "
            "lagere valence-drempel zodat de afspeellijst aansluit bij de huidige gespannen stemming."
        )
    elif stress > 50:
        params.calm_acousticness_min = 0.4
        notes.append("Kalm: licht verhoogde akoestiek-voorkeur (≥0.4) voor matige stress.")

    # --- Energy playlist adjustments ---
    if body_battery < 30:
        params.energy_tempo_min = 110.0
        params.energy_danceability_min = 0.65
        notes.append(
            "Energiek: tempo-minimum verlaagd naar 110 BPM en dansbaarheid verhoogd naar ≥0.65 — "
            "bij lage body battery helpt ritmische consistentie (dansbaarheid) "
            "zonder te agressieve tempostijging."
        )
    elif body_battery < 50:
        params.energy_tempo_min = 115.0
        notes.append("Energiek: tempo-minimum licht verlaagd naar 115 BPM voor gematigde vermoeidheid.")
    elif body_battery > 70:
        params.energy_tempo_min = 130.0
        notes.append(
            "Energiek: tempo-minimum verhoogd naar 130 BPM — "
            "hoge body battery laat een intensere energieopbouw toe."
        )

    # --- Activity-specific note ---
    act_en = _ACTIVITY_EN.get(activity, activity)
    if act_en in ("Sleep", "Rest") and stress < 40:
        notes.append(
            "Tip: bij rust en lage stress kan een neutrale afspeellijst "
            "even effectief zijn als energiek (ISO stabiel)."
        )

    params.context_notes = notes
    return params
