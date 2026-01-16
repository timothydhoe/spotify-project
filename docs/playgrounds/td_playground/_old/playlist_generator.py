"""
Playlist Generator - Create personalized Calm & Upbeat playlists

Filters matched songs into two playlists based on:
- Calm: 50-80 BPM, low energy
- Upbeat: 80-130 BPM, high energy

Validates minimum song count (10 songs per playlist)

Usage:
    python playlist_generator.py --input matched_P001.csv --participant P001
"""

import pandas as pd
import argparse
from pathlib import Path

# Max tempo has to be adjusted according to playlists -> BPM between 50 and 80 is low for general listeners??.
def filter_calm_songs(df, min_tempo=50, max_tempo=110, max_energy=0.8):
    """
    Filter songs suitable for calm/relaxation playlist
    
    Criteria:
    - Tempo: 50-80 BPM (slow, relaxing)
    - Energy: < 0.5 (low energy)
    - Acousticness: prefer > 0.3 (more organic/acoustic)
    """
    filtered = df[
        (df['tempo'].between(min_tempo, max_tempo)) &
        (df['energy'] < max_energy)
    ].copy()
    
    # Bonus: prefer more acoustic songs
    filtered = filtered.sort_values('acousticness', ascending=False)
    
    return filtered


def filter_upbeat_songs(df, min_tempo=110, max_tempo=130, min_energy=0.6):
    """
    Filter songs suitable for upbeat/energizing playlist
    
    Criteria:
    - Tempo: 80-130 BPM (faster, energizing)
    - Energy: > 0.6 (high energy)
    - Valence: prefer > 0.5 (positive/happy)
    """
    filtered = df[
        (df['tempo'].between(min_tempo, max_tempo)) &
        (df['energy'] > min_energy)
    ].copy()
    
    # Bonus: prefer more positive/happy songs
    filtered = filtered.sort_values('valence', ascending=False)
    
    return filtered


def validate_playlist(df, min_songs=10, target_duration_min=30):
    """
    Validate if playlist meets requirements
    
    Returns:
        tuple: (is_valid, message, stats)
    """
    song_count = len(df)
    
    if song_count == 0:
        return False, "No songs match criteria", {}
    
    # Calculate duration
    total_duration_ms = df['duration_ms'].sum()
    total_duration_min = total_duration_ms / 60000
    
    stats = {
        'song_count': song_count,
        'duration_min': round(total_duration_min, 1),
        'avg_tempo': round(df['tempo'].mean(), 1),
        'avg_energy': round(df['energy'].mean(), 2),
        'avg_valence': round(df['valence'].mean(), 2)
    }
    
    # Check minimum songs
    if song_count < min_songs:
        return False, f"Only {song_count} songs (need {min_songs})", stats
    
    # Check duration
    if total_duration_min < (target_duration_min * 0.8):  # Allow 20% under
        return False, f"Only {total_duration_min:.1f} min (need ~{target_duration_min} min)", stats
    
    return True, "OK", stats


def create_playlists(matched_songs, participant_id, output_dir="."):
    """
    Create calm and upbeat playlists from matched songs
    
    Args:
        matched_songs: DataFrame with matched songs + audio features
        participant_id: Participant ID (e.g., "P001")
        output_dir: Directory to save playlist CSVs
        
    Returns:
        dict with calm and upbeat DataFrames
    """
    print(f"\n{'='*60}")
    print(f"GENERATING PLAYLISTS FOR {participant_id}")
    print(f"{'='*60}")
    print(f"Total matched songs: {len(matched_songs)}")
    
    # Filter for each playlist type
    print("\n--- CALM PLAYLIST (Stress Reduction) ---")
    calm_songs = filter_calm_songs(matched_songs)
    print(f"Candidates: {len(calm_songs)} songs")
    
    print("\n--- UPBEAT PLAYLIST (Energy Boost) ---")
    upbeat_songs = filter_upbeat_songs(matched_songs)
    print(f"Candidates: {len(upbeat_songs)} songs")
    
    # Validate playlists
    results = {}
    
    # Calm playlist
    calm_valid, calm_msg, calm_stats = validate_playlist(calm_songs)
    print("\nCALM Playlist Validation:")
    print(f"  Status: {'✓ VALID' if calm_valid else '✗ INVALID'}")
    print(f"  Message: {calm_msg}")
    print(f"  Stats: {calm_stats}")
    
    if calm_valid:
        # Select top 10-12 songs
        calm_playlist = calm_songs.head(12)
        calm_output = Path(output_dir) / f"{participant_id}_calm_playlist.csv"
        calm_playlist.to_csv(calm_output, index=False)
        print(f"  ✓ Saved to: {calm_output}")
        results['calm'] = calm_playlist
    else:
        print("  ⚠ WARNING: Calm playlist doesn't meet requirements")
        results['calm'] = None
    
    # Upbeat playlist
    upbeat_valid, upbeat_msg, upbeat_stats = validate_playlist(upbeat_songs)
    print("\nUPBEAT Playlist Validation:")
    print(f"  Status: {'✓ VALID' if upbeat_valid else '✗ INVALID'}")
    print(f"  Message: {upbeat_msg}")
    print(f"  Stats: {upbeat_stats}")
    
    if upbeat_valid:
        # Select top 10-12 songs
        upbeat_playlist = upbeat_songs.head(12)
        upbeat_output = Path(output_dir) / f"{participant_id}_upbeat_playlist.csv"
        upbeat_playlist.to_csv(upbeat_output, index=False)
        print(f"  ✓ Saved to: {upbeat_output}")
        results['upbeat'] = upbeat_playlist
    else:
        print("  ⚠ WARNING: Upbeat playlist doesn't meet requirements")
        results['upbeat'] = None
    
    # Summary
    print(f"\n{'='*60}")
    print("GENERATION SUMMARY")
    print(f"{'='*60}")
    
    if results['calm'] is not None and results['upbeat'] is not None:
        print("✓ SUCCESS: Both playlists generated")
    elif results['calm'] is not None or results['upbeat'] is not None:
        print("⚠ PARTIAL: Only one playlist generated")
        if results['calm'] is None:
            print("  - Calm playlist: FAILED (not enough songs)")
        if results['upbeat'] is None:
            print("  - Upbeat playlist: FAILED (not enough songs)")
    else:
        print("✗ FAILURE: No playlists generated")
        print("\nPossible reasons:")
        print("  - Participant's music library too small")
        print("  - Music doesn't fit BPM/energy criteria")
        print("  - Need to ask participant for more songs")
    
    return results


def print_playlist_preview(df, playlist_name):
    """Print a preview of the playlist"""
    print(f"\n{'='*60}")
    print(f"{playlist_name} - SONG LIST")
    print(f"{'='*60}")
    
    display_cols = ['name', 'artists', 'tempo', 'energy', 'valence', 'duration_ms']
    preview = df[display_cols].copy()
    preview['duration_min'] = (preview['duration_ms'] / 60000).round(2)
    preview = preview.drop('duration_ms', axis=1)
    
    print(preview.to_string(index=False))
    print(f"\nTotal: {len(df)} songs, {df['duration_ms'].sum()/60000:.1f} minutes")


def main():
    parser = argparse.ArgumentParser(description='Generate calm and upbeat playlists')
    parser.add_argument('--input', required=True, help='Path to matched songs CSV')
    parser.add_argument('--participant', required=True, help='Participant ID (e.g., P001)')
    parser.add_argument('--output-dir', default='.', help='Directory to save playlists (default: current dir)')
    parser.add_argument('--preview', action='store_true', help='Print full playlist previews')
    
    args = parser.parse_args()
    
    # Load matched songs
    print(f"\nLoading matched songs from: {args.input}")
    matched_songs = pd.read_csv(args.input)
    
    # Validate required columns
    required_cols = ['name', 'artists', 'tempo', 'energy', 'valence', 'duration_ms']
    missing_cols = [col for col in required_cols if col not in matched_songs.columns]
    if missing_cols:
        raise ValueError(f"Matched songs CSV missing required columns: {missing_cols}")
    
    print(f"✓ Loaded {len(matched_songs)} matched songs")
    
    # Create output directory if needed
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate playlists
    results = create_playlists(matched_songs, args.participant, output_dir)
    
    # Print previews if requested
    if args.preview:
        if results['calm'] is not None:
            print_playlist_preview(results['calm'], "CALM PLAYLIST")
        if results['upbeat'] is not None:
            print_playlist_preview(results['upbeat'], "UPBEAT PLAYLIST")
    
    print(f"\n{'='*60}")
    print("PLAYLIST GENERATION COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()