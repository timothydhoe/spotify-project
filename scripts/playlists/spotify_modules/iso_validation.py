"""
file: iso_validation.py
-----------------------
Validate and visualize ISO principle adherence in playlists

WHAT THIS MODULE DOES:
1. Validates that playlists follow ISO principle trajectories
2. Calculates ISO adherence scores (0-100)
3. Generates trajectory visualization plots
4. Creates comprehensive validation reports

ISO PRINCIPLE:
- Calm playlists should show DESCENDING tempo/energy (stress -> calm)
- energy playlists should show ASCENDING tempo/energy (tired -> energized)
- Neutral playlists should show CONSISTENT tempo/energy (stable baseline)

WHY THIS MATTERS:
- Ensures playlists follow evidence-based ordering
- Provides quantitative measure of trajectory quality
- Generates proof for research documentation
"""

# import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# import seaborn as sns
# from pathlib import Path


# ============================================================
# CONFIGURATION: ISO Validation Parameters
# ============================================================

# Gradient direction expectations
EXPECTED_DIRECTION = {
    'calm': 'descending',
    'energy': 'ascending',
    'neutral': 'consistent'
}

# Neutral playlist tolerance (for "consistent" trajectory)
NEUTRAL_TEMPO_TOLERANCE = 2.0  # BPM change threshold
NEUTRAL_ENERGY_TOLERANCE = 0.05  # Energy change threshold

# ISO score weights
GRADIENT_SCORE_WEIGHT = 50  # Points for correct gradient direction
SMOOTHNESS_SCORE_WEIGHT = 50  # Points for minimal violations

# Plot styling
PLOT_COLORS = {
    'calm': '#3498db',    # Blue
    'energy': '#e74c3c',  # Red
    'neutral': '#95a5a6'  # Gray
}

PLOT_TITLES = {
    'calm': 'Stress → Calm',
    'energy': 'Tired → Energized',
    'neutral': 'Baseline Control'
}


# ============================================================
# TRAJECTORY CALCULATION
# ============================================================

def calculate_trajectory_metrics(playlist):
    """
    Calculate basic trajectory metrics from playlist
    
    Args:
        playlist: DataFrame with tempo and energy columns
    
    Returns:
        Dict with trajectory metrics or None if too few songs
    """
    if len(playlist) < 2:
        return None
    
    tempos = playlist['tempo'].values
    energies = playlist['energy'].values
    
    # Calculate gradients (change per song)
    tempo_gradient = (tempos[-1] - tempos[0]) / len(tempos)
    energy_gradient = (energies[-1] - energies[0]) / len(energies)
    
    # Calculate smoothness (std of changes between consecutive songs)
    tempo_changes = np.diff(tempos)
    energy_changes = np.diff(energies)
    tempo_std = np.std(tempo_changes)
    energy_std = np.std(energy_changes)
    
    return {
        'tempo_gradient': tempo_gradient,
        'energy_gradient': energy_gradient,
        'tempo_std': tempo_std,
        'energy_std': energy_std,
        'first_tempo': tempos[0],
        'last_tempo': tempos[-1],
        'first_energy': energies[0],
        'last_energy': energies[-1],
        'tempo_changes': tempo_changes,
        'energy_changes': energy_changes
    }


def count_violations(changes, expected_direction):
    """
    Count how many transitions violate the expected direction
    
    Args:
        changes: Array of differences between consecutive songs
        expected_direction: 'ascending', 'descending', or 'consistent'
    
    Returns:
        Number of violations
    """
    if expected_direction == 'descending':
        # Violations are increases when we expect decreases
        return np.sum(changes > 0)
    
    elif expected_direction == 'ascending':
        # Violations are decreases when we expect increases
        return np.sum(changes < 0)
    
    elif expected_direction == 'consistent':
        # For neutral, violations aren't applicable
        return 0
    
    return 0


# ============================================================
# ISO VALIDATION CHECKS
# ============================================================

def check_gradient_direction(metrics, playlist_type):
    """
    Check if gradient matches expected direction for playlist type
    
    Args:
        metrics: Trajectory metrics dict
        playlist_type: 'calm', 'energy', or 'neutral'
    
    Returns:
        Tuple: (tempo_correct, energy_correct)
    """
    tempo_gradient = metrics['tempo_gradient']
    energy_gradient = metrics['energy_gradient']
    
    if playlist_type == 'calm':
        # Should be descending (negative)
        tempo_correct = tempo_gradient < 0
        energy_correct = energy_gradient < 0
    
    elif playlist_type == 'energy':
        # Should be ascending (positive)
        tempo_correct = tempo_gradient > 0
        energy_correct = energy_gradient > 0
    
    elif playlist_type == 'neutral':
        # Should be near-zero (consistent)
        tempo_correct = abs(tempo_gradient) < NEUTRAL_TEMPO_TOLERANCE
        energy_correct = abs(energy_gradient) < NEUTRAL_ENERGY_TOLERANCE
    
    else:
        tempo_correct = False
        energy_correct = False
    
    return tempo_correct, energy_correct


def calculate_iso_score(metrics, playlist_type, tempo_violations, energy_violations, total_transitions):
    """
    Calculate ISO adherence score (0-100)
    
    SCORING SYSTEM:
    - 50 points for correct gradient direction (tempo + energy)
    - 50 points for smoothness (fewer violations)
    
    Args:
        metrics: Trajectory metrics dict
        playlist_type: 'calm', 'energy', or 'neutral'
        tempo_violations: Number of tempo violations
        energy_violations: Number of energy violations
        total_transitions: Total number of song transitions
    
    Returns:
        ISO score (0-100)
    """
    tempo_correct, energy_correct = check_gradient_direction(metrics, playlist_type)
    
    if playlist_type in ['calm', 'energy']:
        # Gradient score: 50 points if both correct
        gradient_score = 0
        if tempo_correct and energy_correct:
            gradient_score = GRADIENT_SCORE_WEIGHT
        
        # Smoothness score: Based on violation rate
        total_violations = tempo_violations + energy_violations
        possible_violations = 2 * total_transitions  # Both tempo and energy
        violation_rate = total_violations / possible_violations if possible_violations > 0 else 0
        smoothness_score = SMOOTHNESS_SCORE_WEIGHT * (1 - violation_rate)
        
        iso_score = gradient_score + smoothness_score
    
    else:  # neutral
        # For neutral, score based on consistency (lower std = higher score)
        tempo_consistency = max(0, 100 * (1 - min(metrics['tempo_std'] / 10, 1)))
        energy_consistency = max(0, 100 * (1 - min(metrics['energy_std'] / 0.1, 1)))
        iso_score = (tempo_consistency + energy_consistency) / 2
    
    return round(iso_score, 1)


# ============================================================
# VALIDATION: Main Function
# ============================================================

def validate_iso_trajectory(playlist, playlist_type='calm'):
    """
    Validate that playlist follows ISO principle
    
    WORKFLOW:
    1. Calculate trajectory metrics
    2. Check gradient direction
    3. Count violations
    4. Calculate ISO score
    5. Generate validation message
    
    Args:
        playlist: DataFrame with tempo and energy columns
        playlist_type: 'calm', 'energy', or 'neutral'
    
    Returns:
        Dict with validation results
    """
    # Basic validation
    if len(playlist) < 2:
        return {
            'valid': False,
            'message': 'Playlist too short for trajectory analysis',
            'metrics': {},
            'type': playlist_type
        }
    
    # Calculate trajectory metrics
    metrics = calculate_trajectory_metrics(playlist)
    
    # Check gradient direction
    tempo_correct, energy_correct = check_gradient_direction(metrics, playlist_type)
    
    # Count violations
    expected = EXPECTED_DIRECTION[playlist_type]
    tempo_violations = count_violations(metrics['tempo_changes'], expected)
    energy_violations = count_violations(metrics['energy_changes'], expected)
    
    # Calculate ISO score
    total_transitions = len(playlist) - 1
    iso_score = calculate_iso_score(
        metrics, playlist_type,
        tempo_violations, energy_violations,
        total_transitions
    )
    
    # Overall validation
    valid = tempo_correct and energy_correct
    
    # Build metrics dict for output
    output_metrics = {
        'tempo_gradient': round(metrics['tempo_gradient'], 2),
        'energy_gradient': round(metrics['energy_gradient'], 3),
        'tempo_std': round(metrics['tempo_std'], 2),
        'energy_std': round(metrics['energy_std'], 3),
        'tempo_violations': tempo_violations,
        'energy_violations': energy_violations,
        'iso_score': iso_score,
        'first_tempo': round(metrics['first_tempo'], 1),
        'last_tempo': round(metrics['last_tempo'], 1),
        'first_energy': round(metrics['first_energy'], 2),
        'last_energy': round(metrics['last_energy'], 2)
    }
    
    # Generate message
    if valid:
        message = f"ISO principle validated - {expected} trajectory"
    else:
        issues = []
        if not tempo_correct:
            issues.append(f"tempo {metrics['tempo_gradient']:+.1f}/song (expected {expected})")
        if not energy_correct:
            issues.append(f"energy {metrics['energy_gradient']:+.2f}/song (expected {expected})")
        message = "ISO issues: " + ", ".join(issues)
    
    return {
        'valid': valid,
        'message': message,
        'metrics': output_metrics,
        'type': playlist_type
    }


# ============================================================
# PLOTTING HELPERS
# ============================================================

def setup_subplot_with_trajectory(ax, positions, values, color, title, ylabel):
    """
    Setup a subplot with trajectory line and trend
    
    Args:
        ax: Matplotlib axis
        positions: Song positions (1, 2, 3, ...)
        values: Feature values to plot
        color: Plot color
        title: Subplot title
        ylabel: Y-axis label
    """
    # Main trajectory line
    ax.plot(positions, values, 'o-', linewidth=2.5, markersize=8, color=color, alpha=0.8)
    ax.fill_between(positions, values, alpha=0.2, color=color)
    
    # Trend line
    z = np.polyfit(positions, values, 1)
    p = np.poly1d(z)
    ax.plot(positions, p(positions), "--", color='gray', linewidth=1.5, alpha=0.7,
            label=f'Trend: {z[0]:+.1f}/song' if ylabel == 'Tempo (BPM)' else f'Trend: {z[0]:+.3f}/song')
    
    # Styling
    ax.set_xlabel('Song Position in Playlist', fontsize=12, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xticks(positions)
    ax.legend(loc='best')


def add_start_end_annotations(ax, positions, values, color):
    """
    Add start and end value annotations to plot
    
    Args:
        ax: Matplotlib axis
        positions: Song positions
        values: Feature values
        color: Annotation color
    """
    # Start annotation
    ax.annotate(
        f'Start\n{values[0]:.1f}' if values[0] > 10 else f'Start\n{values[0]:.2f}',
        xy=(positions[0], values[0]),
        xytext=(10, 10),
        textcoords='offset points',
        bbox=dict(boxstyle='round,pad=0.5', fc=color, alpha=0.3),
        fontsize=10,
        fontweight='bold'
    )
    
    # End annotation
    ax.annotate(
        f'End\n{values[-1]:.1f}' if values[-1] > 10 else f'End\n{values[-1]:.2f}',
        xy=(positions[-1], values[-1]),
        xytext=(-10, 10),
        textcoords='offset points',
        bbox=dict(boxstyle='round,pad=0.5', fc=color, alpha=0.3),
        fontsize=10,
        fontweight='bold',
        ha='right'
    )


# ============================================================
# VISUALIZATION: Individual Plots
# ============================================================

def plot_iso_trajectory(playlist, playlist_type, participant_id, output_path=None):
    """
    Visualize ISO trajectory with tempo and energy over song positions
    
    Args:
        playlist: DataFrame with tempo and energy columns
        playlist_type: 'calm', 'energy', or 'neutral'
        participant_id: Participant code
        output_path: Optional path to save figure
    
    Returns:
        Matplotlib figure
    """
    if len(playlist) < 2:
        print("Playlist too short for trajectory plot")
        return None
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    positions = list(range(1, len(playlist) + 1))
    tempos = playlist['tempo'].values
    energies = playlist['energy'].values
    
    color = PLOT_COLORS.get(playlist_type, '#95a5a6')
    title_suffix = PLOT_TITLES.get(playlist_type, playlist_type)
    
    # Tempo plot
    setup_subplot_with_trajectory(
        ax1, positions, tempos, color,
        f'{playlist_type.upper()} Playlist - Tempo Trajectory\n{participant_id} ({title_suffix})',
        'Tempo (BPM)'
    )
    add_start_end_annotations(ax1, positions, tempos, color)
    
    # Energy plot
    setup_subplot_with_trajectory(
        ax2, positions, energies, color,
        'Energy Trajectory',
        'Energy (0-1 scale)'
    )
    ax2.set_ylim(0, 1)
    add_start_end_annotations(ax2, positions, energies, color)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"ISO trajectory plot saved: {output_path}")
    
    plt.show()
    
    return fig


def plot_combined_iso_comparison(calm_playlist, energy_playlist, neutral_playlist,
                                   participant_id, output_path=None):
    """
    Create comparison plot showing ISO trajectories for all three playlists side-by-side
    
    Args:
        calm_playlist: Calm playlist DataFrame
        energy_playlist: energy playlist DataFrame
        neutral_playlist: Neutral playlist DataFrame
        participant_id: Participant code
        output_path: Optional path to save figure
    
    Returns:
        Matplotlib figure
    """
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f'ISO Principle Comparison - {participant_id}',
                 fontsize=16, fontweight='bold', y=0.995)
    
    playlists = [
        (calm_playlist, 'calm'),
        (energy_playlist, 'energy'),
        (neutral_playlist, 'neutral')
    ]
    
    for idx, (playlist, ptype) in enumerate(playlists):
        if playlist is None or len(playlist) < 2:
            # Show "No Data" message
            for row in [0, 1]:
                axes[row, idx].text(0.5, 0.5, f'{ptype.capitalize()}\nNo Data',
                                   ha='center', va='center', fontsize=14)
                axes[row, idx].set_xticks([])
                axes[row, idx].set_yticks([])
            continue
        
        positions = list(range(1, len(playlist) + 1))
        tempos = playlist['tempo'].values
        energies = playlist['energy'].values
        color = PLOT_COLORS[ptype]
        
        # Tempo subplot
        ax_tempo = axes[0, idx]
        ax_tempo.plot(positions, tempos, 'o-', linewidth=2, markersize=6, color=color, alpha=0.8)
        ax_tempo.fill_between(positions, tempos, alpha=0.2, color=color)
        ax_tempo.set_title(f'{ptype.capitalize()} - Tempo', fontweight='bold')
        ax_tempo.set_xlabel('Song Position')
        ax_tempo.set_ylabel('Tempo (BPM)')
        ax_tempo.grid(True, alpha=0.3)
        
        # Add gradient text
        gradient = (tempos[-1] - tempos[0]) / len(tempos)
        ax_tempo.text(0.05, 0.95, f'Gradient: {gradient:+.1f} BPM/song',
                     transform=ax_tempo.transAxes, fontsize=9,
                     verticalalignment='top',
                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Energy subplot
        ax_energy = axes[1, idx]
        ax_energy.plot(positions, energies, 'o-', linewidth=2, markersize=6, color=color, alpha=0.8)
        ax_energy.fill_between(positions, energies, alpha=0.2, color=color)
        ax_energy.set_title(f'{ptype.capitalize()} - Energy', fontweight='bold')
        ax_energy.set_xlabel('Song Position')
        ax_energy.set_ylabel('Energy (0-1)')
        ax_energy.set_ylim(0, 1)
        ax_energy.grid(True, alpha=0.3)
        
        # Add gradient text
        gradient = (energies[-1] - energies[0]) / len(energies)
        ax_energy.text(0.05, 0.95, f'Gradient: {gradient:+.3f}/song',
                      transform=ax_energy.transAxes, fontsize=9,
                      verticalalignment='top',
                      bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"ISO comparison plot saved: {output_path}")
    
    plt.show()
    
    return fig


# ============================================================
# REPORTING
# ============================================================

def generate_iso_report(calm_playlist, energy_playlist, neutral_playlist, participant_id):
    """
    Generate comprehensive ISO validation report
    
    Args:
        calm_playlist: Calm playlist DataFrame
        energy_playlist: energy playlist DataFrame
        neutral_playlist: Neutral playlist DataFrame
        participant_id: Participant code
    
    Returns:
        Formatted text report string
    """
    report = []
    report.append("=" * 70)
    report.append(f"ISO PRINCIPLE VALIDATION REPORT - {participant_id}")
    report.append("=" * 70)
    report.append("")
    
    # Validate each playlist
    playlists = [
        (calm_playlist, 'calm', 'Calm (Stress → Relaxation)'),
        (energy_playlist, 'energy', 'energy (Tired → Energized)'),
        (neutral_playlist, 'neutral', 'Neutral (Baseline Control)')
    ]
    
    validation_results = []
    
    for playlist, ptype, name in playlists:
        report.append(f"\n{name}")
        report.append("-" * 70)
        
        if playlist is None or len(playlist) < 2:
            report.append("No playlist data available")
            validation_results.append({'type': ptype, 'valid': False, 'iso_score': 0})
            continue
        
        result = validate_iso_trajectory(playlist, ptype)
        validation_results.append(result)
        
        report.append(f"Status: {result['message']}")
        report.append(f"ISO Adherence Score: {result['metrics']['iso_score']}/100")
        report.append("")
        report.append("Trajectory Metrics:")
        report.append(f"  • Tempo: {result['metrics']['first_tempo']} → {result['metrics']['last_tempo']} BPM")
        report.append(f"    Gradient: {result['metrics']['tempo_gradient']:+.2f} BPM/song")
        report.append(f"    Smoothness: σ={result['metrics']['tempo_std']:.2f}")
        
        if ptype != 'neutral':
            report.append(f"    Violations: {result['metrics']['tempo_violations']}/{len(playlist)-1} transitions")
        
        report.append(f"  • Energy: {result['metrics']['first_energy']} → {result['metrics']['last_energy']}")
        report.append(f"    Gradient: {result['metrics']['energy_gradient']:+.3f}/song")
        report.append(f"    Smoothness: σ={result['metrics']['energy_std']:.3f}")
        
        if ptype != 'neutral':
            report.append(f"    Violations: {result['metrics']['energy_violations']}/{len(playlist)-1} transitions")
    
    # Overall summary
    report.append("")
    report.append("=" * 70)
    report.append("OVERALL SUMMARY")
    report.append("=" * 70)
    
    valid_count = sum(1 for r in validation_results if r['valid'])
    avg_iso_score = np.mean([r['iso_score'] for r in validation_results if 'iso_score' in r])
    
    report.append(f"Valid playlists: {valid_count}/3")
    report.append(f"Average ISO score: {avg_iso_score:.1f}/100")
    
    if valid_count == 3:
        report.append("")
        report.append("EXCELLENT: All playlists follow ISO principle")
    elif valid_count >= 2:
        report.append("")
        report.append("GOOD: Most playlists follow ISO principle")
    else:
        report.append("")
        report.append("NEEDS REVIEW: ISO principle not consistently followed")
        report.append("   Consider adjusting song selection or filter criteria")
    
    report.append("=" * 70)
    
    return "\n".join(report)


def save_iso_report(calm_playlist, energy_playlist, neutral_playlist,
                    participant_id, output_path):
    """
    Generate and save ISO validation report to file
    
    Args:
        calm_playlist: Calm playlist DataFrame
        energy_playlist: energy playlist DataFrame
        neutral_playlist: Neutral playlist DataFrame
        participant_id: Participant code
        output_path: Path to save report
    
    Returns:
        Report content string
    """
    report = generate_iso_report(calm_playlist, energy_playlist, neutral_playlist, participant_id)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"ISO validation report saved: {output_path}")
    
    return report


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("ISO Validation Module")
    print("Import this module to validate playlist ISO adherence")
    print("\nExample:")
    print("  from iso_validation import validate_iso_trajectory, plot_iso_trajectory")
    print("  result = validate_iso_trajectory(playlist_df, 'calm')")
    print("  plot_iso_trajectory(playlist_df, 'calm', 'P001')")