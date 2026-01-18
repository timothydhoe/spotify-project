"""
generate.py - Generate personalised calm, neutral, and upbeat playlists

WHAT THIS MODULE DOES:
1. Loads combined song data from prepare step
2. Filters songs into three categories based on tempo/energy
3. Orders songs using ISO principle (gradual transitions)
4. Validates playlist quality
5. Saves playlists to CSV files

ISO PRINCIPLE:
Music interventions work best when they start at the listener's current state
and gradually transition to the desired state:
- Calm: High activation -> Low activation (stress to relaxation)
- Upbeat: Low activation -> High activation (tired to energised)
- Neutral: Consistent medium activation (baseline control)

WHY THREE PLAYLISTS:
- Calm + Upbeat = Different therapeutic goals
- Neutral = Control condition for experimental design
- Personalised = Uses participant's own music library
"""

import pandas as pd
from pathlib import Path


# ============================================================
# CONFIGURATION: Playlist Parameters
# ============================================================

# Number of songs to include in final playlists
PLAYLIST_SIZE = 12

# Minimum requirements for validation
MIN_SONGS_REQUIRED = 10
TARGET_DURATION_MIN = 30

# ISO activation weighting
# Higher weight on tempo means tempo drives the trajectory more than energy
TEMPO_WEIGHT = 0.8
ENERGY_WEIGHT = 0.2


# ============================================================
# FILTERING: Song Selection with ISO Ordering
# ============================================================

def filter_calm_songs(df, min_tempo=50, max_tempo=70, max_energy=0.6, 
                      min_acousticness=0.3, max_valence=0.6, 
                      min_loudness=-20, max_loudness=-8):
    """
    Filter and order songs for calm/relaxation playlist using ISO principle
    
    ISO TRAJECTORY (Stress -> Calm):
    Phase 1 - Ontmoeting (80-100 BPM): Match stressed state
    Phase 2 - De-escalatie (70-80 BPM): Begin calming
    Phase 3 - Regulatie (60-70 BPM): Deep relaxation
    Phase 4 - Landing (50-60 BPM): Final calm state
    
    RESEARCH-BACKED FEATURES:
    - Tempo: 50-70 BPM (lower tempo = relaxation)
    - Energy: <0.6 (softer, less intense)
    - Acousticness: >0.3 (warmer, lower frequencies)
    - Valence: <0.6 (not too energetic/positive)
    - Loudness: -20 to -8 dB (soft but audible)
    
    Args:
        df: DataFrame of all songs
        min_tempo: Minimum BPM threshold (default: 50)
        max_tempo: Maximum BPM threshold (default: 70)
        max_energy: Maximum energy threshold (default: 0.6)
        min_acousticness: Minimum acousticness (default: 0.3)
        max_valence: Maximum valence (default: 0.6)
        min_loudness: Minimum loudness in dB (default: -20)
        max_loudness: Maximum loudness in dB (default: -8)
    
    Returns:
        DataFrame of calm songs, ordered by DESCENDING activation
    """
    # Build filter conditions
    conditions = (
        (df['tempo'].between(min_tempo, max_tempo)) &
        (df['energy'] < max_energy)
    )
    
    # Add optional features if they exist in the dataframe
    if 'acousticness' in df.columns:
        conditions &= (df['acousticness'] > min_acousticness)
    
    if 'valence' in df.columns:
        conditions &= (df['valence'] < max_valence)
    
    if 'loudness' in df.columns:
        conditions &= (df['loudness'].between(min_loudness, max_loudness))
    
    # Apply filters
    filtered = df[conditions].copy()
    
    if len(filtered) == 0:
        return filtered
    
    # Calculate activation score (higher = more energised)
    max_tempo_in_set = filtered['tempo'].max()
    if max_tempo_in_set > 0:
        filtered['activation'] = (
            TEMPO_WEIGHT * (filtered['tempo'] / max_tempo_in_set) +
            ENERGY_WEIGHT * filtered['energy']
        )
    else:
        filtered['activation'] = filtered['energy']
    
    # Sort DESCENDING: Start high activation, end low (stress -> calm)
    filtered = filtered.sort_values(['tempo', 'energy'], ascending=[False, False])
    filtered = filtered.drop('activation', axis=1)
    
    return filtered


def filter_neutral_songs(df, min_tempo=95, max_tempo=115, min_energy=0.5, max_energy=0.7):
    """
    Filter and order songs for neutral/baseline playlist
    
    GOAL: Maintain consistent medium activation (control condition)
    
    Args:
        df: DataFrame of all songs
        min_tempo: Minimum BPM threshold (default: 95)
        max_tempo: Maximum BPM threshold (default: 115)
        min_energy: Minimum energy threshold (default: 0.5)
        max_energy: Maximum energy threshold (default: 0.7)
    
    Returns:
        DataFrame of neutral songs, ordered by consistency
    """
    # Filter by criteria
    filtered = df[
        (df['tempo'].between(min_tempo, max_tempo)) &
        (df['energy'].between(min_energy, max_energy))
    ].copy()
    
    if len(filtered) == 0:
        return filtered
    
    # Calculate consistency score (lower = more consistent)
    target_tempo = (min_tempo + max_tempo) / 2
    target_energy = (min_energy + max_energy) / 2
    
    filtered['consistency'] = (
        abs(filtered['tempo'] - target_tempo) / target_tempo +
        abs(filtered['energy'] - target_energy)
    )
    
    # Sort by consistency (most consistent first)
    filtered = filtered.sort_values('consistency')
    filtered = filtered.drop('consistency', axis=1)
    
    return filtered


def filter_upbeat_songs(df, min_tempo=120, max_tempo=150, min_energy=0.7,
                        min_danceability=0.6, min_valence=0.5, min_loudness=-10):
    """
    Filter and order songs for upbeat/energising playlist using ISO principle
    
    ISO TRAJECTORY (Tired -> Energised):
    Phase 1 - Ontmoeting (70-90 BPM): Match low energy state
    Phase 2 - Activatie (90-110 BPM): Build alertness
    Phase 3 - Energise (110-130 BPM): Strong activation
    Phase 4 - Pieken (130-150 BPM): Peak motivation
    
    RESEARCH-BACKED FEATURES:
    - Tempo: 120-150 BPM (higher tempo = energy boost)
    - Energy: >0.7 (intense, dynamic)
    - Danceability: >0.6 (strong, regular beat)
    - Valence: >0.5 (more positive/energetic)
    - Loudness: >-10 dB (more dynamic)
    
    Args:
        df: DataFrame of all songs
        min_tempo: Minimum BPM threshold (default: 120)
        max_tempo: Maximum BPM threshold (default: 150)
        min_energy: Minimum energy threshold (default: 0.7)
        min_danceability: Minimum danceability (default: 0.6)
        min_valence: Minimum valence (default: 0.5)
        min_loudness: Minimum loudness in dB (default: -10)
    
    Returns:
        DataFrame of upbeat songs, ordered by ASCENDING activation
    """
    # Build filter conditions
    conditions = (
        (df['tempo'].between(min_tempo, max_tempo)) &
        (df['energy'] > min_energy)
    )
    
    # Add optional features if they exist in the dataframe
    if 'danceability' in df.columns:
        conditions &= (df['danceability'] > min_danceability)
    
    if 'valence' in df.columns:
        conditions &= (df['valence'] > min_valence)
    
    if 'loudness' in df.columns:
        conditions &= (df['loudness'] > min_loudness)
    
    # Apply filters
    filtered = df[conditions].copy()
    
    if len(filtered) == 0:
        return filtered
    
    # Calculate activation score (higher = more energised)
    max_tempo_in_set = filtered['tempo'].max()
    if max_tempo_in_set > 0:
        filtered['activation'] = (
            TEMPO_WEIGHT * (filtered['tempo'] / max_tempo_in_set) +
            ENERGY_WEIGHT * filtered['energy']
        )
    else:
        filtered['activation'] = filtered['energy']
    
    # Sort ASCENDING: Start low activation, end high (tired -> energised)
    filtered = filtered.sort_values(['tempo', 'energy'], ascending=[True, True])
    filtered = filtered.drop('activation', axis=1)
    
    return filtered
    filtered = filtered.drop('activation', axis=1)
    
    return filtered


# ============================================================
# VALIDATION: Quality Checks
# ============================================================

def validate_playlist(df, min_songs=MIN_SONGS_REQUIRED, target_duration_min=TARGET_DURATION_MIN):
    """
    Check if playlist meets minimum quality requirements
    
    CHECKS:
    - Enough songs (10+)
    - Sufficient duration (30 min target)
    
    Args:
        df: Playlist DataFrame
        min_songs: Minimum song count required
        target_duration_min: Target duration in minutes
    
    Returns:
        Tuple: (is_valid, message, stats_dict)
    """
    song_count = len(df)
    
    if song_count == 0:
        return False, "No songs match criteria", {}
    
    # Calculate statistics
    total_duration_ms = df['duration_ms'].sum() if 'duration_ms' in df.columns else 0
    total_duration_min = total_duration_ms / 60000
    
    stats = {
        'songs': song_count,
        'duration': round(total_duration_min, 1),
        'avg_tempo': round(df['tempo'].mean(), 1) if 'tempo' in df.columns else 0,
        'avg_energy': round(df['energy'].mean(), 2) if 'energy' in df.columns else 0
    }
    
    # Check minimum songs
    if song_count < min_songs:
        return False, f"Only {song_count}/{min_songs} songs", stats
    
    # Check minimum duration (allow 80% of target)
    if total_duration_min < (target_duration_min * 0.8):
        return False, f"Only {total_duration_min:.1f}/{target_duration_min} min", stats
    
    return True, "OK", stats


def calculate_iso_metrics(playlist):
    """
    Calculate ISO trajectory metrics for a playlist
    
    Args:
        playlist: DataFrame with ordered songs
    
    Returns:
        Dict with trajectory metrics or None if too few songs
    """
    if len(playlist) < 2:
        return None
    
    first_tempo = playlist.iloc[0]['tempo']
    last_tempo = playlist.iloc[-1]['tempo']
    gradient = (last_tempo - first_tempo) / len(playlist)
    
    return {
        'first_tempo': first_tempo,
        'last_tempo': last_tempo,
        'gradient': gradient
    }


def calculate_consistency_metrics(playlist):
    """
    Calculate consistency metrics for neutral playlist
    
    Args:
        playlist: DataFrame with ordered songs
    
    Returns:
        Dict with consistency metrics or None if too few songs
    """
    if len(playlist) < 2:
        return None
    
    tempo_std = playlist['tempo'].std()
    energy_std = playlist['energy'].std()
    
    return {
        'tempo_std': tempo_std,
        'energy_std': energy_std
    }


# ============================================================
# OUTPUT: Printing and Saving
# ============================================================

def print_playlist_header(playlist_type):
    """Print section header for a playlist type"""
    titles = {
        'calm': 'CALM PLAYLIST (Stress -> Relaxation)',
        'neutral': 'NEUTRAL PLAYLIST (Baseline Control)',
        'upbeat': 'UPBEAT PLAYLIST (Tired -> Energised)'
    }
    
    print(f"\n{'='*50}")
    print(titles.get(playlist_type, playlist_type.upper()))
    print(f"{'='*50}")


def print_validation_status(is_valid, message):
    """Print validation status with appropriate symbol"""
    status_symbol = 'OK' if is_valid else 'X'
    print(f"Status: {status_symbol} {message}")


def print_playlist_stats(stats):
    """Print basic playlist statistics"""
    print(f"  {stats['songs']} songs, {stats['duration']} min")
    print(f"  Avg: {stats['avg_tempo']} BPM, {stats['avg_energy']} energy")


def print_iso_trajectory(metrics):
    """Print ISO trajectory information"""
    if metrics:
        print(f"  ISO trajectory: {metrics['first_tempo']:.1f} -> "
              f"{metrics['last_tempo']:.1f} BPM "
              f"(gradient: {metrics['gradient']:.1f}/song)")


def print_consistency(metrics):
    """Print consistency metrics for neutral playlist"""
    if metrics:
        print(f"  Consistency: Tempo σ={metrics['tempo_std']:.1f}, "
              f"Energy σ={metrics['energy_std']:.2f}")


def print_playlist_preview(playlist):
    """Print detailed song list preview"""
    print("\n" + playlist[['name', 'artists', 'tempo', 'energy']].to_string(index=False))


def save_playlist(playlist, output_dir, participant_id, playlist_type):
    """
    Save playlist to CSV file
    
    Args:
        playlist: DataFrame to save
        output_dir: Output directory path
        participant_id: Participant code
        playlist_type: 'calm', 'neutral', or 'upbeat'
    
    Returns:
        Path to saved file
    """
    output_dir = Path(output_dir)
    filename = f"{participant_id}_{playlist_type}_playlist.csv"
    output_path = output_dir / filename
    
    playlist.to_csv(output_path, index=False)
    print(f"  -> Saved: {filename}")
    
    return output_path


# ============================================================
# PLAYLIST PROCESSING: Unified Handler
# ============================================================

def process_single_playlist(candidates, playlist_type, output_dir, participant_id, preview=False):
    """
    Process a single playlist: validate, select top songs, print info, save
    
    This function handles all three playlist types uniformly, reducing code duplication.
    
    Args:
        candidates: DataFrame of filtered candidate songs
        playlist_type: 'calm', 'neutral', or 'upbeat'
        output_dir: Output directory path
        participant_id: Participant code
        preview: Whether to show detailed song list
    
    Returns:
        Final playlist DataFrame or None if validation failed
    """
    # Print header
    print_playlist_header(playlist_type)
    
    # Validate
    is_valid, message, stats = validate_playlist(candidates)
    print_validation_status(is_valid, message)
    
    if not is_valid:
        print(f"  Warning: {stats}")
        return None
    
    # Print basic stats
    print_playlist_stats(stats)
    
    # Select top songs
    final_playlist = candidates.head(PLAYLIST_SIZE)
    
    # Print trajectory or consistency info
    if playlist_type == 'neutral':
        metrics = calculate_consistency_metrics(final_playlist)
        print_consistency(metrics)
    else:
        metrics = calculate_iso_metrics(final_playlist)
        print_iso_trajectory(metrics)
    
    # Save to file
    save_playlist(final_playlist, output_dir, participant_id, playlist_type)
    
    # Optional preview
    if preview:
        print_playlist_preview(final_playlist)
    
    return final_playlist


# ============================================================
# MAIN FUNCTION: Orchestration
# ============================================================

def generate_playlists(output_dir, participant_id, params, preview=False):
    """
    Generate calm, neutral, and upbeat playlists from combined songs
    
    WORKFLOW:
    1. Load combined song data
    2. Filter songs into three categories (calm, neutral, upbeat)
    3. Order songs using ISO principle
    4. Validate each playlist
    5. Save playlists to CSV files
    
    Args:
        output_dir: Path to playlists_generated folder
        participant_id: Participant code (e.g., aardbei, bosbes)
        params: Dict with 'calm', 'neutral', and 'upbeat' parameter dicts
        preview: Show detailed song lists
    
    Returns:
        Dict with playlist DataFrames (or None for failed playlists)
    """
    output_dir = Path(output_dir)
    combined_path = output_dir / 'combined.csv'
    
    # Check if prepared data exists
    if not combined_path.exists():
        raise FileNotFoundError(
            f"Combined CSV not found: {combined_path}\n"
            "Run 'prepare' command first."
        )
    
    # Load all songs
    all_songs = pd.read_csv(combined_path)
    required_cols = ['name', 'artists', 'tempo', 'energy', 'duration_ms']
    missing = [col for col in required_cols if col not in all_songs.columns]
    
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    print(f"Loaded {len(all_songs)} songs for {participant_id}")
    
    # --------------------------------------------------------
    # STEP 1: Filter songs into three categories
    # --------------------------------------------------------
    
    calm_candidates = filter_calm_songs(all_songs, **params['calm'])
    neutral_candidates = filter_neutral_songs(all_songs, **params['neutral'])
    upbeat_candidates = filter_upbeat_songs(all_songs, **params['upbeat'])
    
    print(f"\nCalm candidates: {len(calm_candidates)} (ISO: high->low activation)")
    print(f"Neutral candidates: {len(neutral_candidates)} (consistent medium)")
    print(f"Upbeat candidates: {len(upbeat_candidates)} (ISO: low->high activation)")
    
    # --------------------------------------------------------
    # STEP 2: Process each playlist type
    # --------------------------------------------------------
    
    results = {}
    
    results['calm'] = process_single_playlist(
        calm_candidates, 'calm', output_dir, participant_id, preview
    )
    
    results['neutral'] = process_single_playlist(
        neutral_candidates, 'neutral', output_dir, participant_id, preview
    )
    
    results['upbeat'] = process_single_playlist(
        upbeat_candidates, 'upbeat', output_dir, participant_id, preview
    )
    
    # --------------------------------------------------------
    # STEP 3: Print summary
    # --------------------------------------------------------
    
    print(f"\n{'='*50}")
    successful = sum(1 for v in results.values() if v is not None)
    
    if successful == 3:
        print("All three playlists generated with ISO ordering")
    elif successful >= 2:
        print(f"Partial success - {successful}/3 playlists generated")
    else:
        print("Failed - participant needs more songs or different criteria")
    print(f"{'='*50}\n")
    
    return results