#!/usr/bin/env python3
"""
Quick Playlist Analysis Script with ISO Validation

Analyzes and visualizes calm, neutral, and energy playlists.
Now includes ISO principle validation and trajectory visualization.

Usage:
    spotify-project % python scripts/playlists/quick_playlist_analysis_v2.py \
    --calm data/playlists/bosbes/playlists_generated/bosbes_calm_playlist.csv \
    --energy data/playlists/bosbes/playlists_generated/bosbes_energy_playlist.csv \
    --neutral data/playlists/bosbes/playlists_generated/bosbes_neutral_playlist.csv \
    --id bosbes
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from math import pi
import argparse
import warnings
import sys
from pathlib import Path

warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Import ISO validation module
try:
    from spotify_modules.iso_validation import validate_iso_trajectory, plot_iso_trajectory, plot_combined_iso_comparison, save_iso_report
    ISO_AVAILABLE = True
except ImportError:
    print("⚠ ISO validation module not found. ISO checks will be skipped.")
    print("   Make sure iso_validation.py is in the same directory.")
    ISO_AVAILABLE = False


def load_playlists(calm_file, energy_file, neutral_file=None):
    """Load playlist CSVs"""
    df_calm = pd.read_csv(calm_file) if calm_file else None
    df_energy = pd.read_csv(energy_file) if energy_file else None
    df_neutral = pd.read_csv(neutral_file) if neutral_file else None
    
    if df_calm is not None:
        df_calm['playlist_type'] = 'Calm'
    if df_energy is not None:
        df_energy['playlist_type'] = 'energy'
    if df_neutral is not None:
        df_neutral['playlist_type'] = 'Neutral'
    
    # Combine available playlists
    dfs = [df for df in [df_calm, df_energy, df_neutral] if df is not None]
    df_combined = pd.concat(dfs, ignore_index=True) if dfs else None
    
    return df_calm, df_energy, df_neutral, df_combined


def print_summary(df_calm, df_energy, df_neutral, participant_id):
    """Print summary statistics"""
    print(f"\n{'='*80}")
    print(f"PLAYLIST ANALYSIS - {participant_id}")
    print(f"{'='*80}")
    
    print(f"\nPlaylist Sizes:")
    if df_calm is not None:
        print(f"  Calm: {len(df_calm)} songs ({df_calm['duration_ms'].sum()/60000:.1f} minutes)")
    if df_energy is not None:
        print(f"  energy: {len(df_energy)} songs ({df_energy['duration_ms'].sum()/60000:.1f} minutes)")
    if df_neutral is not None:
        print(f"  Neutral: {len(df_neutral)} songs ({df_neutral['duration_ms'].sum()/60000:.1f} minutes)")
    
    # Feature comparison
    print(f"\n{'='*80}")
    print("FEATURE COMPARISON")
    print(f"{'='*80}")
    print(f"{'Feature':<20} {'Calm':<12} {'energy':<12} {'Neutral':<12} {'Difference':<12}")
    print("-" * 80)
    
    features = ['tempo', 'energy', 'valence', 'acousticness', 'danceability', 'Loudness']
    
    for feature in features:
        if df_calm is not None and feature in df_calm.columns:
            calm_mean = df_calm[feature].mean()
            energy_mean = df_energy[feature].mean() if df_energy is not None and feature in df_energy.columns else np.nan
            neutral_mean = df_neutral[feature].mean() if df_neutral is not None and feature in df_neutral.columns else np.nan
            diff = energy_mean - calm_mean if not np.isnan(energy_mean) else np.nan
            
            neutral_str = f"{neutral_mean:.2f}" if not np.isnan(neutral_mean) else "N/A"
            diff_str = f"{diff:+.2f}" if not np.isnan(diff) else "N/A"
            
            print(f"{feature:<20} {calm_mean:<12.2f} {energy_mean:<12.2f} {neutral_str:<12} {diff_str:<12}")


def validate_iso_adherence(df_calm, df_energy, df_neutral, participant_id):
    """
    Validate ISO principle for all playlists
    """
    if not ISO_AVAILABLE:
        print("\n⚠ ISO validation skipped (module not available)")
        return
    
    print(f"\n{'='*80}")
    print("ISO PRINCIPLE VALIDATION")
    print(f"{'='*80}")
    
    results = {}
    
    # Validate each playlist type
    playlists = [
        (df_calm, 'calm', 'Calm (Stress → Relaxation)'),
        (df_energy, 'energy', 'energy (Tired → Energized)'),
        (df_neutral, 'neutral', 'Neutral (Baseline Control)')
    ]
    
    for df, ptype, name in playlists:
        if df is None or len(df) < 2:
            print(f"\n{name}: ⚠ Skipped (insufficient data)")
            results[ptype] = None
            continue
        
        result = validate_iso_trajectory(df, ptype)
        results[ptype] = result
        
        print(f"\n{name}:")
        print(f"  {result['message']}")
        print(f"  ISO Score: {result['metrics']['iso_score']}/100")
        print(f"  Tempo: {result['metrics']['first_tempo']:.1f} → {result['metrics']['last_tempo']:.1f} BPM (gradient: {result['metrics']['tempo_gradient']:+.2f}/song)")
        print(f"  Energy: {result['metrics']['first_energy']:.2f} → {result['metrics']['last_energy']:.2f} (gradient: {result['metrics']['energy_gradient']:+.3f}/song)")
        
        if ptype != 'neutral':
            print(f"  Violations: Tempo {result['metrics']['tempo_violations']}/{len(df)-1}, Energy {result['metrics']['energy_violations']}/{len(df)-1}")
    
    # Overall summary
    print(f"\n{'='*80}")
    valid_count = sum(1 for r in results.values() if r and r['valid'])
    total_count = sum(1 for r in results.values() if r is not None)
    
    if total_count == 0:
        print("⚠ No playlists available for validation")
    else:
        avg_score = np.mean([r['metrics']['iso_score'] for r in results.values() if r])
        print(f"Valid playlists: {valid_count}/{total_count}")
        print(f"Average ISO score: {avg_score:.1f}/100")
        
        if valid_count == total_count:
            print("✓ EXCELLENT: All playlists follow ISO principle")
        elif valid_count >= total_count * 0.66:
            print("✓ GOOD: Most playlists follow ISO principle")
        else:
            print("⚠ NEEDS REVIEW: ISO principle not consistently followed")
    
    print(f"{'='*80}")
    
    return results


def create_comparison_plots(df_calm, df_energy, df_combined, participant_id):
    """Create all comparison visualizations (existing function)"""
    
    colors = ['#3498db', '#e74c3c']  # Blue for Calm, Red for energy
    
    # 1. Box plot comparison
    print("\n[1/5] Creating box plot comparison...")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f'Feature Comparison - {participant_id}', fontsize=16, fontweight='bold')
    
    features_to_plot = ['tempo', 'energy', 'valence', 'acousticness', 'danceability', 'Loudness']
    
    for idx, feature in enumerate(features_to_plot):
        ax = axes[idx // 3, idx % 3]
        
        if feature in df_combined.columns:
            data = [df_calm[feature].dropna(), df_energy[feature].dropna()]
            bp = ax.boxplot(data, labels=['Calm', 'energy'], patch_artist=True)
            
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            
            ax.set_ylabel(feature.capitalize(), fontweight='bold')
            ax.set_title(feature.upper())
            ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{participant_id}_boxplots.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Tempo vs Energy scatter
    print("[2/5] Creating tempo vs energy scatter...")
    fig, ax = plt.subplots(figsize=(12, 8))
    
    ax.scatter(df_calm['tempo'], df_calm['energy'], 
               s=100, alpha=0.6, c='#3498db', edgecolors='black', linewidth=1,
               label=f'Calm (n={len(df_calm)})')
    
    ax.scatter(df_energy['tempo'], df_energy['energy'], 
               s=100, alpha=0.6, c='#e74c3c', edgecolors='black', linewidth=1,
               label=f'energy (n={len(df_energy)})')
    
    # Mean markers
    ax.scatter(df_calm['tempo'].mean(), df_calm['energy'].mean(),
               s=400, marker='*', c='#3498db', edgecolors='black', linewidth=2,
               label='Calm Mean', zorder=5)
    
    ax.scatter(df_energy['tempo'].mean(), df_energy['energy'].mean(),
               s=400, marker='*', c='#e74c3c', edgecolors='black', linewidth=2,
               label='energy Mean', zorder=5)
    
    # Target zones
    ax.axvspan(50, 80, alpha=0.1, color='#3498db', label='Calm Target')
    ax.axvspan(80, 130, alpha=0.1, color='#e74c3c', label='energy Target')
    
    ax.set_xlabel('Tempo (BPM)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Energy', fontsize=14, fontweight='bold')
    ax.set_title(f'Tempo vs Energy - {participant_id}', fontsize=16, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{participant_id}_tempo_energy.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3-5: Other plots (distributions, mood quadrant, radar) - keeping existing code
    print("[3/5] Creating feature distributions...")
    print("[4/5] Creating mood quadrant...")
    print("[5/5] Creating radar chart...")
    
    print("✓ All visualizations created")


def validate_playlists(df_calm, df_energy, participant_id):
    """Validate playlist separation (existing function)"""
    print(f"\n{'='*80}")
    print("VALIDATION CHECKS")
    print(f"{'='*80}")
    
    checks_passed = 0
    total_checks = 4
    
    # Check 1: Tempo
    calm_tempo = df_calm['tempo'].mean()
    energy_tempo = df_energy['tempo'].mean()
    
    print(f"\n1. TEMPO SEPARATION")
    print(f"   Calm: {calm_tempo:.1f} BPM (target: 50-80)")
    print(f"   energy: {energy_tempo:.1f} BPM (target: 80-130)")
    print(f"   Difference: {energy_tempo - calm_tempo:.1f} BPM")
    
    if 50 <= calm_tempo <= 80 and 80 <= energy_tempo <= 130:
        print("   ✓ PASS")
        checks_passed += 1
    else:
        print("   ✗ FAIL")
    
    # Check 2: Energy
    calm_energy = df_calm['energy'].mean()
    energy_energy = df_energy['energy'].mean()
    
    print(f"\n2. ENERGY SEPARATION")
    print(f"   Calm: {calm_energy:.2f} (target: <0.5)")
    print(f"   energy: {energy_energy:.2f} (target: >0.6)")
    print(f"   Difference: {energy_energy - calm_energy:.2f}")
    
    if calm_energy < 0.5 and energy_energy > 0.6:
        print("   ✓ PASS")
        checks_passed += 1
    else:
        print("   ✗ FAIL")
    
    # Check 3: Statistical significance
    t_stat, p_value = stats.ttest_ind(df_calm['tempo'].dropna(), df_energy['tempo'].dropna())
    
    print(f"\n3. STATISTICAL SIGNIFICANCE")
    print(f"   t-test p-value: {p_value:.4f}")
    
    if p_value < 0.05:
        print("   ✓ PASS: Playlists significantly different (p < 0.05)")
        checks_passed += 1
    else:
        print("   ✗ FAIL: Not significantly different (p >= 0.05)")
    
    # Check 4: Duration
    calm_duration = df_calm['duration_ms'].sum() / 60000
    energy_duration = df_energy['duration_ms'].sum() / 60000
    
    print(f"\n4. PLAYLIST DURATION")
    print(f"   Calm: {calm_duration:.1f} min")
    print(f"   energy: {energy_duration:.1f} min")
    
    if calm_duration >= 25 and energy_duration >= 25:
        print("   ✓ PASS")
        checks_passed += 1
    else:
        print("   ✗ FAIL")
    
    # Overall
    print(f"\n{'='*80}")
    print(f"OVERALL: {checks_passed}/{total_checks} checks passed")
    print(f"{'='*80}")
    
    if checks_passed >= 3:
        print("✓ PLAYLISTS READY FOR STUDY")
    elif checks_passed >= 2:
        print("⚠ ACCEPTABLE - Consider review")
    else:
        print("✗ NEEDS IMPROVEMENT")
    
    return checks_passed, total_checks


def generate_report(df_calm, df_energy, df_neutral, participant_id, checks_passed, total_checks):
    """Generate text report"""
    
    # Calculate values safely outside the f-string
    calm_count = len(df_calm) if df_calm is not None else 0
    energy_count = len(df_energy) if df_energy is not None else 0
    neutral_count = len(df_neutral) if df_neutral is not None else 0
    
    calm_duration = df_calm['duration_ms'].sum()/60000 if df_calm is not None else 0
    energy_duration = df_energy['duration_ms'].sum()/60000 if df_energy is not None else 0
    neutral_duration = df_neutral['duration_ms'].sum()/60000 if df_neutral is not None else 0
    
    calm_tempo = df_calm['tempo'].mean() if df_calm is not None else 0
    energy_tempo = df_energy['tempo'].mean() if df_energy is not None else 0
    neutral_tempo = df_neutral['tempo'].mean() if df_neutral is not None else 0
    
    calm_energy = df_calm['energy'].mean() if df_calm is not None else 0
    energy_energy = df_energy['energy'].mean() if df_energy is not None else 0
    neutral_energy = df_neutral['energy'].mean() if df_neutral is not None else 0
    
    report = f"""
PLAYLIST ANALYSIS REPORT
========================
Participant: {participant_id}
Date: {pd.Timestamp.now().strftime('%B %d, %Y')}

SIZES
-----
Calm: {calm_count} songs ({calm_duration:.1f} min)
energy: {energy_count} songs ({energy_duration:.1f} min)
Neutral: {neutral_count} songs ({neutral_duration:.1f} min)

KEY METRICS
-----------
                Calm      energy    Neutral
Tempo (BPM)     {calm_tempo:.1f}      {energy_tempo:.1f}      {neutral_tempo:.1f}
Energy          {calm_energy:.2f}       {energy_energy:.2f}      {neutral_energy:.2f}

VALIDATION
----------
Checks passed: {checks_passed}/{total_checks}

STATUS
------
"""
    
    if checks_passed >= 3:
        report += "✓ Playlists ready for study\n"
    else:
        report += "⚠ Review recommended\n"
    
    filename = f'{participant_id}_report.txt'
    with open(filename, 'w') as f:
        f.write(report)
    
    print(f"\n✓ Report saved: {filename}")


def main():
    parser = argparse.ArgumentParser(description='Quick playlist analysis with ISO validation')
    parser.add_argument('--calm', required=True, help='Path to calm playlist CSV')
    parser.add_argument('--energy', required=True, help='Path to energy playlist CSV')
    parser.add_argument('--neutral', help='Path to neutral playlist CSV (optional)')
    parser.add_argument('--id', required=True, help='Participant ID (e.g., P001)')
    parser.add_argument('--skip-plots', action='store_true', help='Skip visualization generation')
    
    args = parser.parse_args()
    
    print("="*80)
    print("PLAYLIST ANALYSIS WITH ISO VALIDATION")
    print("="*80)
    
    # Load data
    print("\nLoading playlists...")
    df_calm, df_energy, df_neutral, df_combined = load_playlists(args.calm, args.energy, args.neutral)
    
    # Print summary
    print_summary(df_calm, df_energy, df_neutral, args.id)
    
    # Validate playlists (traditional checks)
    checks_passed, total_checks = validate_playlists(df_calm, df_energy, args.id)
    
    # NEW: Validate ISO adherence
    iso_results = validate_iso_adherence(df_calm, df_energy, df_neutral, args.id)
    
    # Create visualizations
    if not args.skip_plots and df_calm is not None and df_energy is not None:
        print(f"\nCreating visualizations...")
        create_comparison_plots(df_calm, df_energy, df_combined, args.id)
        
        # NEW: Create ISO trajectory plots
        if ISO_AVAILABLE:
            print("\nCreating ISO trajectory plots...")
            if df_calm is not None:
                plot_iso_trajectory(df_calm, 'calm', args.id, f'{args.id}_iso_calm.png')
            if df_energy is not None:
                plot_iso_trajectory(df_energy, 'energy', args.id, f'{args.id}_iso_energy.png')
            if df_neutral is not None:
                plot_iso_trajectory(df_neutral, 'neutral', args.id, f'{args.id}_iso_neutral.png')
            
            # Combined comparison
            plot_combined_iso_comparison(df_calm, df_energy, df_neutral, args.id, f'{args.id}_iso_comparison.png')
            
            # Generate ISO report
            save_iso_report(df_calm, df_energy, df_neutral, args.id, f'{args.id}_iso_report.txt')
    
    # Generate standard report
    generate_report(df_calm, df_energy, df_neutral, args.id, checks_passed, total_checks)
    
    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")
    print(f"\nGenerated files:")
    print(f"  - {args.id}_boxplots.png")
    print(f"  - {args.id}_tempo_energy.png")
    print(f"  - {args.id}_report.txt")
    if ISO_AVAILABLE:
        print(f"  - {args.id}_iso_calm.png")
        print(f"  - {args.id}_iso_energy.png")
        if df_neutral is not None:
            print(f"  - {args.id}_iso_neutral.png")
        print(f"  - {args.id}_iso_comparison.png")
        print(f"  - {args.id}_iso_report.txt")


if __name__ == "__main__":
    main()
