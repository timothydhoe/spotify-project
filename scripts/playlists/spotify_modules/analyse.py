"""
File: analyse.py
----------------
Analyse and visualise generated playlists

WHAT THIS MODULE DOES:
1. Loads calm, neutral, and upbeat playlists
2. Calculates comparison statistics
3. Validates playlist separation quality
4. Generates 4 visualizations (boxplots, scatter, distributions, mood quadrant)
5. Creates a summary text report

WHY THIS MATTERS:
- Validates that playlists are sufficiently different
- Ensures measurable intervention effects
- Provides visual proof of separation for research documentation
"""
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path




# ============================================================
# CONFIGURATION: Analysis Settings
# ============================================================

# Features to analyze and compare
FEATURES_TO_ANALYZE = ['tempo', 'energy', 'valence', 'acousticness', 'danceability', 'loudness', 'speechiness']
FEATURES_FOR_PLOTS = ['tempo', 'energy', 'valence', 'acousticness', 'danceability', 'loudness']
FEATURES_FOR_DISTRIBUTIONS = ['tempo', 'energy', 'valence', 'acousticness']

# Plot styling
PLOT_COLORS = {
    'Calm': 'blue',
    'Neutral': 'gray',
    'Upbeat': 'red'
}

PLOT_MARKERS = {
    'Calm': 'o',
    'Neutral': 's',
    'Upbeat': '^'
}

# Validation thresholds
TEMPO_RANGES = {
    'calm': (50, 110),
    'neutral': (95, 115),
    'upbeat': (110, 130)
}

ENERGY_THRESHOLDS = {
    'calm': (0, 0.8),
    'upbeat': (0.6, 1.0)
}

MIN_TEMPO_DIFFERENCE = 15  # BPM between calm and upbeat
MIN_DURATION_MINUTES = 25


# ============================================================
# DATA LOADING
# ============================================================

def load_playlists(output_dir, participant_id):
    """
    Load calm, neutral, and upbeat playlists from CSV files
    
    Args:
        output_dir: Path to playlists_generated folder
        participant_id: Participant code
    
    Returns:
        Tuple: (dataframes_dict, combined_df, playlists_found_list)
    """
    output_dir = Path(output_dir)
    
    # Define file paths
    files = {
        'calm': output_dir / f"{participant_id}_calm_playlist.csv",
        'neutral': output_dir / f"{participant_id}_neutral_playlist.csv",
        'upbeat': output_dir / f"{participant_id}_upbeat_playlist.csv"
    }
    
    # Load available playlists
    dataframes = {}
    playlists_found = []
    
    for playlist_type, filepath in files.items():
        if filepath.exists():
            df = pd.read_csv(filepath)
            df['playlist_type'] = playlist_type.capitalize()
            dataframes[playlist_type] = df
            playlists_found.append(playlist_type)
    
    if not playlists_found:
        raise FileNotFoundError(f"No playlist files found in {output_dir}")
    
    # Combine for comparison plots
    combined_df = pd.concat(dataframes.values(), ignore_index=True)
    
    return dataframes, combined_df, playlists_found


# ============================================================
# STATISTICS CALCULATION
# ============================================================

def calculate_statistics(dataframes):
    """
    Calculate summary statistics for all playlists
    
    Args:
        dataframes: Dict of playlist DataFrames
    
    Returns:
        Dict with statistics for each feature
    """
    stats = {}
    
    for feature in FEATURES_TO_ANALYZE:
        stats[feature] = {}
        
        for playlist_type, df in dataframes.items():
            if feature in df.columns:
                stats[feature][f'{playlist_type}_mean'] = df[feature].mean()
                stats[feature][f'{playlist_type}_std'] = df[feature].std()
    
    return stats


# ============================================================
# VALIDATION CHECKS
# ============================================================

def check_tempo_ranges(dataframes, stats):
    """
    Check if each playlist's tempo falls within expected range
    
    Returns:
        Tuple: (passed, details_string)
    """
    if 'tempo' not in stats:
        return False, "No tempo data"
    
    all_ok = True
    
    for playlist_type, (min_tempo, max_tempo) in TEMPO_RANGES.items():
        if playlist_type in dataframes:
            mean_tempo = stats['tempo'].get(f'{playlist_type}_mean', 0)
            if not (min_tempo <= mean_tempo <= max_tempo):
                all_ok = False
    
    return all_ok, "Tempo ranges appropriate"


def check_energy_separation(dataframes, stats):
    """
    Check if calm and upbeat playlists have proper energy separation
    
    Returns:
        Tuple: (passed, details_string)
    """
    if 'energy' not in stats:
        return False, "No energy data"
    
    all_ok = True
    
    if 'calm' in dataframes:
        calm_energy = stats['energy'].get('calm_mean', 0)
        if calm_energy >= ENERGY_THRESHOLDS['calm'][1]:
            all_ok = False
    
    if 'upbeat' in dataframes:
        upbeat_energy = stats['energy'].get('upbeat_mean', 0)
        if upbeat_energy <= ENERGY_THRESHOLDS['upbeat'][0]:
            all_ok = False
    
    return all_ok, "Energy separation adequate"


def check_tempo_difference(dataframes, stats):
    """
    Check if calm and upbeat have substantial tempo difference
    
    Returns:
        Tuple: (passed, details_string)
    """
    if 'tempo' not in stats or 'calm' not in dataframes or 'upbeat' not in dataframes:
        return True, "Cannot check (playlists missing)"
    
    calm_tempo = stats['tempo'].get('calm_mean', 0)
    upbeat_tempo = stats['tempo'].get('upbeat_mean', 0)
    difference = upbeat_tempo - calm_tempo
    
    passed = difference >= MIN_TEMPO_DIFFERENCE
    
    return passed, f"Tempo difference: {difference:.1f} BPM"


def check_duration_requirements(dataframes):
    """
    Check if all playlists meet minimum duration
    
    Returns:
        Tuple: (passed, details_string)
    """
    all_ok = True
    
    for playlist_type, df in dataframes.items():
        if 'duration_ms' in df.columns:
            duration_min = df['duration_ms'].sum() / 60000
            if duration_min < MIN_DURATION_MINUTES:
                all_ok = False
    
    return all_ok, "Duration requirements met"


def validate_separation(dataframes, stats):
    """
    Run all validation checks on playlist separation
    
    Args:
        dataframes: Dict of playlist DataFrames
        stats: Statistics dict
    
    Returns:
        Tuple: (checks_passed, total_checks, validation_results_list)
    """
    # Run all checks
    checks = [
        ("Tempo ranges", check_tempo_ranges(dataframes, stats)),
        ("Energy separation", check_energy_separation(dataframes, stats)),
        ("Substantial tempo difference", check_tempo_difference(dataframes, stats)),
        ("Duration requirements", check_duration_requirements(dataframes))
    ]
    
    # Count passed checks
    checks_passed = sum(1 for _, (passed, _) in checks if passed)
    total_checks = len(checks)
    
    # Format results
    validation_results = [(name, passed) for name, (passed, _) in checks]
    
    return checks_passed, total_checks, validation_results


# ============================================================
# VISUALIZATION HELPERS
# ============================================================

def setup_plot_style():
    """Configure matplotlib style for all plots"""
    plt.style.use('seaborn-v0_8-whitegrid')


def save_figure(fig, output_dir, filename):
    """
    Save figure to output directory
    
    Args:
        fig: Matplotlib figure
        output_dir: Output directory path
        filename: Output filename
    """
    output_path = Path(output_dir) / filename
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return output_path


# ============================================================
# INDIVIDUAL VISUALIZATIONS
# ============================================================

def create_boxplot_comparison(df_combined, participant_id, output_dir):
    """
    Create boxplot comparison of features across playlist types
    
    Args:
        df_combined: Combined DataFrame with all playlists
        participant_id: Participant code
        output_dir: Output directory path
    
    Returns:
        Path to saved figure
    """
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle(f'{participant_id} - Feature Comparison', fontsize=16, fontweight='bold')
    
    for idx, feature in enumerate(FEATURES_FOR_PLOTS):
        ax = axes[idx // 3, idx % 3]
        
        if feature in df_combined.columns:
            # Get colors for each playlist type
            palette = [PLOT_COLORS.get(pt, 'black') for pt in df_combined['playlist_type'].unique()]
            
            sns.boxplot(
                data=df_combined,
                x='playlist_type',
                y=feature,
                hue='playlist_type',
                ax=ax,
                palette=palette,
                legend=False
            )
            ax.set_title(feature.capitalize(), fontweight='bold')
            ax.set_xlabel('')
    
    plt.tight_layout()
    
    return save_figure(fig, output_dir, f"{participant_id}_feature_comparison.jpg")


def create_tempo_energy_scatter(df_combined, participant_id, output_dir):
    """
    Create tempo vs energy scatter plot
    
    Args:
        df_combined: Combined DataFrame with all playlists
        participant_id: Participant code
        output_dir: Output directory path
    
    Returns:
        Path to saved figure
    """
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot each playlist type
    for playlist_type, color in PLOT_COLORS.items():
        if playlist_type in df_combined['playlist_type'].values:
            data = df_combined[df_combined['playlist_type'] == playlist_type]
            ax.scatter(
                data['tempo'],
                data['energy'],
                alpha=0.6,
                s=100,
                c=color,
                label=playlist_type,
                edgecolors='black'
            )
    
    ax.set_xlabel('Tempo (BPM)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Energy', fontsize=12, fontweight='bold')
    ax.set_title(f'{participant_id} - Tempo vs Energy', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    return save_figure(fig, output_dir, f"{participant_id}_tempo_energy.jpg")


def create_distributions(df_combined, participant_id, output_dir):
    """
    Create feature distribution histograms
    
    Args:
        df_combined: Combined DataFrame with all playlists
        participant_id: Participant code
        output_dir: Output directory path
    
    Returns:
        Path to saved figure
    """
    import matplotlib.pyplot as plt
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(f'{participant_id} - Feature Distributions', fontsize=16, fontweight='bold')
    
    for idx, feature in enumerate(FEATURES_FOR_DISTRIBUTIONS):
        ax = axes[idx // 2, idx % 2]
        
        if feature in df_combined.columns:
            for playlist_type, color in PLOT_COLORS.items():
                if playlist_type in df_combined['playlist_type'].values:
                    data = df_combined[df_combined['playlist_type'] == playlist_type][feature]
                    ax.hist(data, alpha=0.5, bins=10, label=playlist_type, color=color)
            
            ax.set_xlabel(feature.capitalize(), fontweight='bold')
            ax.set_ylabel('Count')
            ax.set_title(feature.capitalize())
            ax.legend()
    
    plt.tight_layout()
    
    return save_figure(fig, output_dir, f"{participant_id}_distributions.jpg")


def create_mood_quadrant(df_combined, participant_id, output_dir):
    """
    Create mood quadrant plot (valence vs energy)
    
    Args:
        df_combined: Combined DataFrame with all playlists
        participant_id: Participant code
        output_dir: Output directory path
    
    Returns:
        Path to saved figure
    """
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot each playlist type with different markers
    for playlist_type, color in PLOT_COLORS.items():
        if playlist_type in df_combined['playlist_type'].values:
            data = df_combined[df_combined['playlist_type'] == playlist_type]
            marker = PLOT_MARKERS.get(playlist_type, 'o')
            
            ax.scatter(
                data['valence'],
                data['energy'],
                alpha=0.6,
                s=100,
                c=color,
                marker=marker,
                label=playlist_type,
                edgecolors='black'
            )
    
    # Add quadrant lines
    ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5)
    
    # Label quadrants
    quadrant_labels = [
        (0.75, 0.75, 'Happy\nEnergetic'),
        (0.25, 0.75, 'Turbulent\nAngry'),
        (0.25, 0.25, 'Sad\nDepressed'),
        (0.75, 0.25, 'Chill\nPeaceful')
    ]
    
    for x, y, label in quadrant_labels:
        ax.text(x, y, label, ha='center', va='center', alpha=0.3, fontsize=10)
    
    ax.set_xlabel('Valence (Mood)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Energy', fontsize=12, fontweight='bold')
    ax.set_title(f'{participant_id} - Mood Quadrant Analysis', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    return save_figure(fig, output_dir, f"{participant_id}_mood_quadrant.jpg")


def create_visualisations(dataframes, df_combined, participant_id, output_dir):
    """
    Generate all visualization plots
    
    Creates 4 plots:
    1. Feature comparison boxplots
    2. Tempo vs energy scatter
    3. Feature distributions
    4. Mood quadrant analysis
    
    Args:
        dataframes: Dict of individual playlist DataFrames
        df_combined: Combined DataFrame
        participant_id: Participant code
        output_dir: Output directory path
    
    Returns:
        List of created file paths
    """
    setup_plot_style()
    
    created_files = []
    
    # Create each visualization
    created_files.append(create_boxplot_comparison(df_combined, participant_id, output_dir))
    created_files.append(create_tempo_energy_scatter(df_combined, participant_id, output_dir))
    created_files.append(create_distributions(df_combined, participant_id, output_dir))
    created_files.append(create_mood_quadrant(df_combined, participant_id, output_dir))
    
    # Print summary
    print(f"\nGenerated {len(created_files)} visualisation files:")
    for filepath in created_files:
        print(f"  - {filepath.name}")
    
    return created_files


# ============================================================
# REPORT GENERATION
# ============================================================

def format_feature_table(stats, dataframes):
    """
    Format feature comparison table for report
    
    Args:
        stats: Statistics dict
        dataframes: Dict of playlist DataFrames
    
    Returns:
        Formatted string table
    """
    lines = []
    
    features_to_report = ['tempo', 'energy', 'valence', 'acousticness', 'danceability']
    
    for feature in features_to_report:
        if feature not in stats:
            continue
        
        feature_label = 'Tempo (BPM)' if feature == 'tempo' else feature.capitalize()
        line = f"{feature_label:20s}"
        
        for playlist_type in ['calm', 'neutral', 'upbeat']:
            if playlist_type in dataframes:
                mean_val = stats[feature].get(f'{playlist_type}_mean', 0)
                if feature == 'tempo':
                    line += f"  {mean_val:6.1f}"
                else:
                    line += f"  {mean_val:6.2f}"
        
        lines.append(line)
    
    return "\n".join(lines)


def generate_report(participant_id, dataframes, stats, validation_results, checks_passed, total_checks, output_dir):
    """
    Generate text summary report
    
    Args:
        participant_id: Participant code
        dataframes: Dict of playlist DataFrames
        stats: Statistics dict
        validation_results: List of validation check results
        checks_passed: Number of checks passed
        total_checks: Total number of checks
        output_dir: Output directory path
    
    Returns:
        Path to saved report
    """
    output_dir = Path(output_dir)
    
    # Build report content
    lines = [
        "",
        "PLAYLIST ANALYSIS REPORT",
        "=" * 60,
        f"Participant: {participant_id}",
        f"Date: {datetime.today().strftime('%Y-%m-%d')}",
        "",
        "PLAYLIST SIZES",
        "-" * 60
    ]
    
    # Add playlist sizes
    for playlist_type, df in dataframes.items():
        duration = df['duration_ms'].sum() / 60000 if 'duration_ms' in df.columns else 0
        lines.append(f"{playlist_type.capitalize()}: {len(df)} songs ({duration:.1f} minutes)")
    
    # Add feature comparison
    lines.extend([
        "",
        "KEY METRICS (Mean Values)",
        "-" * 60,
        format_feature_table(stats, dataframes)
    ])
    
    # Add validation results
    lines.extend([
        "",
        "VALIDATION RESULTS",
        "-" * 60
    ])
    
    for check_name, passed in validation_results:
        status = 'OK' if passed else 'X'
        lines.append(f"{status} {check_name}")
    
    lines.append(f"\nChecks passed: {checks_passed}/{total_checks}")
    
    # Add conclusion
    lines.extend([
        "",
        "CONCLUSION",
        "-" * 60
    ])
    
    if checks_passed >= 3:
        lines.append("Playlists show clear separation - suitable for study")
    elif checks_passed >= 2:
        lines.append("Acceptable separation - consider reviewing parameters")
    else:
        lines.append("Insufficient separation - adjust parameters or request more songs")
    
    # Save report
    report_content = "\n".join(lines)
    report_path = output_dir / f"{participant_id}_analysis_report.txt"
    
    with open(report_path, 'w') as f:
        f.write(report_content)
    
    print(f"\nAnalysis report: {report_path.name}")
    
    return report_path


# ============================================================
# MAIN FUNCTION: Orchestration
# ============================================================

def analyse_playlists(output_dir, participant_id, generate_viz=True):
    """
    Analyse and visualise generated playlists
    
    WORKFLOW:
    1. Load calm, neutral, and upbeat playlists
    2. Calculate comparison statistics
    3. Validate playlist separation
    4. Generate visualizations (optional)
    5. Create summary report
    
    Args:
        output_dir: Path to playlists_generated folder
        participant_id: Participant code
        generate_viz: Whether to create visualization plots
    """
    print(f"\nAnalysing playlists for {participant_id}...")
    
    # --------------------------------------------------------
    # STEP 1: Load data
    # --------------------------------------------------------
    
    dataframes, df_combined, playlists_found = load_playlists(output_dir, participant_id)
    playlist_summary = ' + '.join([f'{len(dataframes[p])} {p}' for p in playlists_found])
    print(f"Loaded: {playlist_summary} songs")
    
    # --------------------------------------------------------
    # STEP 2: Calculate statistics
    # --------------------------------------------------------
    
    stats = calculate_statistics(dataframes)
    
    # --------------------------------------------------------
    # STEP 3: Validate separation
    # --------------------------------------------------------
    
    checks_passed, total_checks, validation_results = validate_separation(dataframes, stats)
    
    # Print summary to console
    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*60}")
    
    if 'tempo' in stats:
        tempo_parts = []
        for ptype in ['calm', 'neutral', 'upbeat']:
            if ptype in dataframes:
                tempo = stats['tempo'].get(f'{ptype}_mean', 0)
                tempo_parts.append(f"{tempo:.1f} BPM ({ptype})")
        print(f"Tempo:  {' -> '.join(tempo_parts)}")
    
    if 'energy' in stats:
        energy_parts = []
        for ptype in ['calm', 'neutral', 'upbeat']:
            if ptype in dataframes:
                energy = stats['energy'].get(f'{ptype}_mean', 0)
                energy_parts.append(f"{energy:.2f} ({ptype})")
        print(f"Energy: {' -> '.join(energy_parts)}")
    
    print(f"\nValidation: {checks_passed}/{total_checks} checks passed")
    
    for check_name, passed in validation_results:
        status = 'OK' if passed else 'X'
        print(f"  {status} {check_name}")
    
    # --------------------------------------------------------
    # STEP 4: Generate visualizations (optional)
    # --------------------------------------------------------
    
    if generate_viz:
        print(f"\n{'='*60}")
        print("GENERATING VISUALISATIONS")
        print(f"{'='*60}")
        create_visualisations(dataframes, df_combined, participant_id, output_dir)
    
    # --------------------------------------------------------
    # STEP 5: Generate report
    # --------------------------------------------------------
    
    print(f"\n{'='*60}")
    print("GENERATING REPORT")
    print(f"{'='*60}")
    generate_report(
        participant_id, dataframes, stats,
        validation_results, checks_passed, total_checks, output_dir
    )
    
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}\n")