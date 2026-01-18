"""
File: Outlier Detection for Playlists
-------------------------------------
Identifies statistical outliers in generated playlists and shows their impact
on ISO trajectories and overall playlist quality.

USAGE:
    python outlier_detection.py \
        --playlist path/to/playlist.csv \
        --type calm \
        --features tempo energy
eg:
    python scripts/playlists/outlier_detection.py \
    --playlist data/playlists/bosbes/playlists_generated/bosbes_calm_playlist.csv \
    --type calm

WHAT IT DOES:
- Identifies outliers using IQR method (same as boxplots)
- Shows which songs are outliers and why
- Calculates impact on ISO trajectory
- Optionally generates cleaned playlist
"""

import pandas as pd
import numpy as np
import argparse
# from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

# IQR multiplier for outlier detection
# Standard: 1.5 (boxplot default)
# Conservative: 2.0 (fewer outliers)
# Aggressive: 1.0 (more outliers)
IQR_MULTIPLIER = 1.5

# Features to check for outliers
DEFAULT_FEATURES = ['tempo', 'energy', 'valence', 'acousticness', 'danceability', 'loudness']


# ============================================================
# OUTLIER DETECTION
# ============================================================

def detect_outliers_iqr(data, multiplier=IQR_MULTIPLIER):
    """
    Detect outliers using Interquartile Range (IQR) method
    
    This is the same method used by boxplots:
    - Q1 = 25th percentile
    - Q3 = 75th percentile
    - IQR = Q3 - Q1
    - Lower bound = Q1 - (multiplier * IQR)
    - Upper bound = Q3 + (multiplier * IQR)
    - Outliers = values outside bounds
    
    Args:
        data: Array of values
        multiplier: IQR multiplier (default: 1.5)
    
    Returns:
        Boolean array (True = outlier)
    """
    Q1 = np.percentile(data, 25)
    Q3 = np.percentile(data, 75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - (multiplier * IQR)
    upper_bound = Q3 + (multiplier * IQR)
    
    outliers = (data < lower_bound) | (data > upper_bound)
    
    return outliers, lower_bound, upper_bound


def find_outliers_in_playlist(df, features=None):
    """
    Find all outliers in a playlist across multiple features
    
    Args:
        df: Playlist DataFrame
        features: List of features to check (default: all available)
    
    Returns:
        DataFrame with outlier information
    """
    if features is None:
        features = [f for f in DEFAULT_FEATURES if f in df.columns]
    
    outlier_info = []
    
    for feature in features:
        if feature not in df.columns:
            continue
        
        is_outlier, lower, upper = detect_outliers_iqr(df[feature].values)
        
        # Record outlier songs
        for idx, is_out in enumerate(is_outlier):
            if is_out:
                outlier_info.append({
                    'index': idx,
                    'song': df.iloc[idx]['name'],
                    'feature': feature,
                    'value': df.iloc[idx][feature],
                    'lower_bound': lower,
                    'upper_bound': upper,
                    'direction': 'high' if df.iloc[idx][feature] > upper else 'low'
                })
    
    return pd.DataFrame(outlier_info)


# ============================================================
# IMPACT ANALYSIS
# ============================================================

def calculate_iso_gradient(df):
    """
    Calculate ISO trajectory gradient
    
    Args:
        df: Playlist DataFrame (ordered)
    
    Returns:
        Dict with gradient metrics
    """
    if len(df) < 2:
        return None
    
    first_tempo = df.iloc[0]['tempo']
    last_tempo = df.iloc[-1]['tempo']
    gradient = (last_tempo - first_tempo) / len(df)
    
    return {
        'first_tempo': first_tempo,
        'last_tempo': last_tempo,
        'gradient': gradient,
        'range': last_tempo - first_tempo
    }


def analyze_outlier_impact(df, outlier_indices, playlist_type):
    """
    Analyze how removing outliers would affect the playlist
    
    Args:
        df: Original playlist DataFrame
        outlier_indices: Indices of outlier songs
        playlist_type: 'calm', 'upbeat', or 'neutral'
    
    Returns:
        Dict with impact analysis
    """
    # Original metrics
    original_gradient = calculate_iso_gradient(df)
    original_count = len(df)
    original_duration = df['duration_ms'].sum() / 60000
    
    # Metrics without outliers
    df_clean = df.drop(outlier_indices).reset_index(drop=True)
    clean_gradient = calculate_iso_gradient(df_clean) if len(df_clean) >= 2 else None
    clean_count = len(df_clean)
    clean_duration = df_clean['duration_ms'].sum() / 60000 if len(df_clean) > 0 else 0
    
    # Check gradient direction
    expected_direction = 'descending' if playlist_type == 'calm' else 'ascending' if playlist_type == 'upbeat' else 'consistent'
    
    original_correct = (
        (expected_direction == 'descending' and original_gradient['gradient'] < 0) or
        (expected_direction == 'ascending' and original_gradient['gradient'] > 0)
    ) if original_gradient else False
    
    clean_correct = (
        (expected_direction == 'descending' and clean_gradient['gradient'] < 0) or
        (expected_direction == 'ascending' and clean_gradient['gradient'] > 0)
    ) if clean_gradient else False
    
    return {
        'original': {
            'count': original_count,
            'duration': original_duration,
            'gradient': original_gradient,
            'correct_direction': original_correct
        },
        'cleaned': {
            'count': clean_count,
            'duration': clean_duration,
            'gradient': clean_gradient,
            'correct_direction': clean_correct
        },
        'removed': len(outlier_indices),
        'improvement': clean_correct and not original_correct
    }


# ============================================================
# REPORTING
# ============================================================

def print_outlier_report(df, outliers_df, impact, playlist_type):
    """
    Print comprehensive outlier analysis report
    
    Args:
        df: Playlist DataFrame
        outliers_df: DataFrame with outlier information
        impact: Impact analysis dict
        playlist_type: 'calm', 'upbeat', or 'neutral'
    """
    print(f"\n{'='*70}")
    print(f"OUTLIER DETECTION REPORT - {playlist_type.upper()} PLAYLIST")
    print(f"{'='*70}")
    
    # Summary
    unique_outlier_songs = outliers_df['index'].nunique() if len(outliers_df) > 0 else 0
    total_outlier_detections = len(outliers_df)
    
    print("\nSUMMARY")
    print(f"{'-'*70}")
    print(f"Total songs: {len(df)}")
    print(f"Outlier songs: {unique_outlier_songs} ({unique_outlier_songs/len(df)*100:.1f}%)")
    print(f"Total outlier detections: {total_outlier_detections} (song can be outlier in multiple features)")
    
    # Outlier details
    if len(outliers_df) > 0:
        print()
        print(f"{'-'*70}")
        
        # Group by song
        for song_idx in outliers_df['index'].unique():
            song_outliers = outliers_df[outliers_df['index'] == song_idx]
            song_name = song_outliers.iloc[0]['song']
            
            print(f"\n{song_idx+1}. {song_name}")
            for _, row in song_outliers.iterrows():
                print(f"   • {row['feature']}: {row['value']:.2f} ({row['direction']} outlier)")
                print(f"     Valid range: {row['lower_bound']:.2f} - {row['upper_bound']:.2f}")
    else:
        print("\n✓ No outliers detected!")
    
    # Impact analysis
    print("\nIMPACT ANALYSIS")
    print(f"{'-'*70}")
    
    orig = impact['original']
    clean = impact['cleaned']
    
    print("Original playlist:")
    print(f"  • Songs: {orig['count']}")
    print(f"  • Duration: {orig['duration']:.1f} min")
    if orig['gradient']:
        print(f"  • ISO gradient: {orig['gradient']['gradient']:.2f} BPM/song")
        print(f"  • Trajectory: {orig['gradient']['first_tempo']:.1f} → {orig['gradient']['last_tempo']:.1f} BPM")
        direction = "✓" if orig['correct_direction'] else "✗"
        print(f"  • Direction: {direction} {'Correct' if orig['correct_direction'] else 'Incorrect'}")
    
    print("\nWithout outliers:")
    print(f"  • Songs: {clean['count']} ({impact['removed']} removed)")
    print(f"  • Duration: {clean['duration']:.1f} min ({orig['duration'] - clean['duration']:.1f} min lost)")
    if clean['gradient']:
        print(f"  • ISO gradient: {clean['gradient']['gradient']:.2f} BPM/song")
        print(f"  • Trajectory: {clean['gradient']['first_tempo']:.1f} → {clean['gradient']['last_tempo']:.1f} BPM")
        direction = "✓" if clean['correct_direction'] else "✗"
        print(f"  • Direction: {direction} {'Correct' if clean['correct_direction'] else 'Incorrect'}")
    
    # Recommendation
    print("\nRECOMMENDATION")
    print(f"{'-'*70}")
    
    if unique_outlier_songs == 0:
        print("✓ No outliers - playlist is statistically consistent")
    elif impact['improvement']:
        print("⚠️ Removing outliers IMPROVES ISO trajectory direction")
        print("   → Consider regenerating without these songs")
    elif unique_outlier_songs <= 2 and orig['correct_direction']:
        print("✓ Few outliers and trajectory is correct")
        print("   → Outliers add variety, keep them unless they seem wrong")
    else:
        print("⚠️ Multiple outliers detected")
        print("   → Review outlier songs - are they musically appropriate?")
        print("   → If trajectory is correct, outliers might add valuable variety")


def save_cleaned_playlist(df, outlier_indices, output_path):
    """
    Save playlist without outliers
    
    Args:
        df: Original playlist DataFrame
        outlier_indices: Indices to remove
        output_path: Where to save cleaned playlist
    
    Returns:
        Cleaned DataFrame
    """
    df_clean = df.drop(outlier_indices).reset_index(drop=True)
    df_clean.to_csv(output_path, index=False)
    print(f"\n✓ Cleaned playlist saved: {output_path}")
    return df_clean


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Detect and analyze outliers in generated playlists',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Detect outliers in calm playlist
  python outlier_detection.py \\
    --playlist data/playlists/bosbes/playlists_generated/bosbes_calm_playlist.csv \\
    --type calm
  
  # Check specific features only
  python outlier_detection.py \\
    --playlist bosbes_upbeat_playlist.csv \\
    --type upbeat \\
    --features tempo energy
  
  # Generate cleaned playlist
  python outlier_detection.py \\
    --playlist bosbes_calm_playlist.csv \\
    --type calm \\
    --save-clean bosbes_calm_cleaned.csv
        """
    )
    
    parser.add_argument('--playlist', required=True, help='Path to playlist CSV file')
    parser.add_argument('--type', required=True, choices=['calm', 'upbeat', 'neutral'],
                       help='Playlist type (affects ISO trajectory analysis)')
    parser.add_argument('--features', nargs='+', 
                       help='Features to check for outliers (default: all available)')
    parser.add_argument('--iqr-multiplier', type=float, default=IQR_MULTIPLIER,
                       help=f'IQR multiplier for outlier detection (default: {IQR_MULTIPLIER})')
    parser.add_argument('--save-clean', help='Save cleaned playlist to this path')
    
    args = parser.parse_args()
    
    # Load playlist
    df = pd.read_csv(args.playlist)
    print(f"Loaded playlist: {args.playlist}")
    print(f"Songs: {len(df)}")
    
    # Detect outliers
    outliers_df = find_outliers_in_playlist(df, args.features)
    
    # Get unique outlier song indices
    outlier_indices = outliers_df['index'].unique().tolist() if len(outliers_df) > 0 else []
    
    # Analyze impact
    impact = analyze_outlier_impact(df, outlier_indices, args.type)
    
    # Print report
    print_outlier_report(df, outliers_df, impact, args.type)
    
    # Save cleaned playlist if requested
    if args.save_clean and len(outlier_indices) > 0:
        save_cleaned_playlist(df, outlier_indices, args.save_clean)
    elif args.save_clean and len(outlier_indices) == 0:
        print("\n✓ No outliers to remove - cleaned playlist would be identical")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()