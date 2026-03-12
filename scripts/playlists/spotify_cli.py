"""
File: spotify_cli.py

SOURCE parameters: https://developer.spotify.com/documentation/web-api/reference/get-audio-features

CLI used to combine the modules: prepare.py, generate.py and analyse.py.
Create personalised calm, neutral, and energy playlists from your Spotify data.

QUICK START:
    spotify_cli.py all aardbei

This processes your Spotify CSVs and generates three playlists optimised for:
- Calm: Stress reduction (lower tempo/energy)
- Neutral: Baseline control (medium tempo/energy)
- energy: Energy boost (higher tempo/energy)

For more options, run: spotify_cli.py --help
"""

import argparse
import sys
from pathlib import Path

# Import playlist modules
from spotify_modules.prepare import prepare_csvs
from spotify_modules.generate import generate_playlists
from spotify_modules.analyse import analyse_playlists


# ============================================================
# CONFIGURATION
# ============================================================

# Default playlist parameters based on research:
# "Muzikale Parameters en ISO-Opbouw voor Emotieregulatie via Muziek"
#
# RESEARCH-BACKED RANGES:
# - Calm: 50-70 BPM (stress reduction, activates relaxation networks)
# - Energy: 120-150 BPM (energy boost, activates alertness networks)
# - Neutral: 95-115 BPM (baseline control, medium activation)
#
# Additional features based on scientific literature:
# - Acousticness: Warmer, lower frequencies (calm) vs sharper attack (energy)
# - Valence: Emotional positivity (lower for calm, higher for energy)
# - Loudness: Dynamic range (quieter for calm, more dynamic for energy)
#
DEFAULT_PARAMS = {
    'calm': {
        'min_tempo': 50,
        'max_tempo': 95,          # Research: 50-90 BPM for stress reduction (RAISED)
        'max_energy': 0.9,        # Lower than before
        'min_acousticness': 0,  # Warmer sound, lower frequencies (LOWERED)
        'min_valence': 0.0,       # Raised valence for positive connotation
        'max_valence': 1.0,       # (RAISED)
        'min_loudness': -70,      # Audible but soft
        'max_loudness': 0        # Not too loud
    },
    'neutral': {
        'min_tempo': 95,
        'max_tempo': 115,
        'min_energy': 0.2,
        'max_energy': 0.8
    },
    'energy': {
        'min_tempo': 120,         # Research: 120-150 BPM for energy boost (LOWERED)
        'max_tempo': 180,         # Increased from 130 (RAISED)
        'min_energy': 0.7,        # more energetic
        'min_danceability': 0.5,  # Strong, regular beat
        'min_valence': 0.6,       # More positive/energetic (RAISED)
        'min_loudness': -10       # More dynamic
    }
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def resolve_paths(codename):
    """
    Determine input and output directories based on participant codename
    
    FOLDER STRUCTURE:
    data/playlists/[codename]/              <- Input CSVs
    data/playlists/[cod
    ename]/playlists_generated/  <- Output playlists
    
    Args:
        codename: Participant codename (e.g., aardbei, bosbes)
    
    Returns:
        Tuple: (input_dir, output_dir)
    """
    # Find project root (2 levels up from scripts/playlists/)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.parent
    
    # Set paths
    input_dir = project_root / 'data' / 'playlists' / codename
    output_dir = input_dir / 'playlists_generated'
    
    return input_dir, output_dir


def validate_input_exists(input_dir, codename):
    """
    Check if input directory exists and has CSV files
    
    Args:
        input_dir: Path to participant folder
        codename: Participant codename
    
    Returns:
        Tuple: (is_valid, error_message)
    """
    if not input_dir.exists():
        return False, (
            f"Cannot find folder for '{codename}'.\n"
            f"Expected location: {input_dir}\n\n"
            f"TIP: Create the folder and add Spotify CSV files:\n"
            f"  mkdir -p {input_dir}\n"
            f"  mv your_spotify_files/*.csv {input_dir}/"
        )
    
    csv_files = list(input_dir.glob("*.csv"))
    if not csv_files:
        return False, (
            f"Found folder but no CSV files in: {input_dir}\n\n"
            f"TIP: Add your Spotify Exportify CSVs to this folder."
        )
    
    return True, ""


def validate_prepared_data(output_dir, codename):
    """
    Check if prepare step has been run (combined.csv exists)
    
    Args:
        output_dir: Path to playlists_generated folder
        codename: Participant codename
    
    Returns:
        Tuple: (is_valid, error_message)
    """
    combined_path = output_dir / 'combined.csv'
    
    if not combined_path.exists():
        return False, (
            f"Cannot find prepared data for '{codename}'.\n\n"
            f"TIP: Run the 'prepare' step first:\n"
            f"  spotify_cli.py prepare {codename}\n\n"
            f"Or use 'all' to run everything:\n"
            f"  spotify_cli.py all {codename}"
        )
    
    return True, ""


def build_params_from_args(args):
    """
    Build parameters dict from command line arguments
    
    Args:
        args: Parsed command line arguments
    
    Returns:
        Dict with calm, neutral, and energy parameters
    """
    params = {
        'calm': {
            'min_tempo': args.calm_tempo_min,
            'max_tempo': args.calm_tempo_max,
            'max_energy': args.calm_energy_max,
            # New research-backed parameters
            'min_acousticness': getattr(args, 'calm_acousticness_min', DEFAULT_PARAMS['calm']['min_acousticness']),
            'min_valence': getattr(args, 'calm_valence_min', DEFAULT_PARAMS['calm']['min_valence']),
            'max_valence': getattr(args, 'calm_valence_max', DEFAULT_PARAMS['calm']['max_valence']),
            'min_loudness': getattr(args, 'calm_loudness_min', DEFAULT_PARAMS['calm']['min_loudness']),
            'max_loudness': getattr(args, 'calm_loudness_max', DEFAULT_PARAMS['calm']['max_loudness'])
        },
        'neutral': {
            'min_tempo': args.neutral_tempo_min,
            'max_tempo': args.neutral_tempo_max,
            'min_energy': args.neutral_energy_min,
            'max_energy': args.neutral_energy_max
        },
        'energy': {
            'min_tempo': args.energy_tempo_min,
            'max_tempo': args.energy_tempo_max,
            'min_energy': args.energy_energy_min,
            # New research-backed parameters
            'min_danceability': getattr(args, 'energy_danceability_min', DEFAULT_PARAMS['energy']['min_danceability']),
            'min_valence': getattr(args, 'energy_valence_min', DEFAULT_PARAMS['energy']['min_valence']),
            'min_loudness': getattr(args, 'energy_loudness_min', DEFAULT_PARAMS['energy']['min_loudness'])
        }
    }
    return params


def print_dry_run_info(codename, input_dir, output_dir):
    """
    Print information about what would happen (for --dry-run)
    
    Args:
        codename: Participant codename
        input_dir: Input directory path
        output_dir: Output directory path
    """
    print("\nDRY RUN MODE - No files will be modified")
    print("=" * 60)
    print(f"\nParticipant: {codename}")
    print(f"Input folder: {input_dir}")
    print(f"Output folder: {output_dir}")
    
    # Check what CSV files exist
    if input_dir.exists():
        csv_files = list(input_dir.glob("*.csv"))
        print(f"\nFound {len(csv_files)} CSV file(s):")
        for f in csv_files[:5]:  # Show first 5
            print(f"  - {f.name}")
        if len(csv_files) > 5:
            print(f"  ... and {len(csv_files) - 5} more")
    else:
        print("\nInput folder does not exist yet.")
    
    # Check if already prepared
    if (output_dir / 'combined.csv').exists():
        print("\nPrepared data already exists (combined.csv)")
    else:
        print("\nNo prepared data yet - would run 'prepare' step")
    
    print("\n" + "=" * 60)
    print("To actually run, remove --dry-run flag")
    print("=" * 60 + "\n")


# ============================================================
# COMMAND EXECUTION
# ============================================================

def execute_prepare(args):
    """Execute the prepare command"""
    input_dir, output_dir = resolve_paths(args.codename)
    
    # Validate input
    is_valid, error_msg = validate_input_exists(input_dir, args.codename)
    if not is_valid:
        print(f"\nERROR: {error_msg}\n", file=sys.stderr)
        sys.exit(1)
    
    # Run prepare
    prepare_csvs(input_dir, output_dir)


def execute_generate(args):
    """Execute the generate command"""
    input_dir, output_dir = resolve_paths(args.codename)
    
    # Determine participant ID
    participant_id = args.participant if args.participant else args.codename
    
    # Validate prepared data exists
    is_valid, error_msg = validate_prepared_data(output_dir, args.codename)
    if not is_valid:
        print(f"\nERROR: {error_msg}\n", file=sys.stderr)
        sys.exit(1)
    
    # Build parameters
    params = build_params_from_args(args)
    
    # Run generate
    generate_playlists(output_dir, participant_id, params, args.preview)


def execute_analyse(args):
    """Execute the analyse command"""
    input_dir, output_dir = resolve_paths(args.codename)
    
    # Determine participant ID
    participant_id = args.participant if args.participant else args.codename
    
    # Validate playlists exist
    playlist_files = list(output_dir.glob(f"{participant_id}_*_playlist.csv"))
    if not playlist_files:
        print(
            f"\nERROR: No playlists found for '{participant_id}'.\n\n"
            f"TIP: Run 'generate' first:\n"
            f"  spotify_cli.py generate {args.codename}\n\n"
            f"Or use 'all' to run everything:\n"
            f"  spotify_cli.py all {args.codename}\n",
            file=sys.stderr
        )
        sys.exit(1)
    
    # Run analyse
    analyse_playlists(output_dir, participant_id, not args.no_viz)


def execute_all(args):
    """Execute complete workflow: prepare -> generate -> analyse"""
    input_dir, output_dir = resolve_paths(args.codename)
    
    # Determine participant ID
    participant_id = args.participant if args.participant else args.codename
    
    # Dry run mode
    if args.dry_run:
        print_dry_run_info(args.codename, input_dir, output_dir)
        return
    
    # Validate input exists
    is_valid, error_msg = validate_input_exists(input_dir, args.codename)
    if not is_valid:
        print(f"\nERROR: {error_msg}\n", file=sys.stderr)
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print(f"RUNNING COMPLETE WORKFLOW FOR {participant_id.upper()}")
    print("=" * 60 + "\n")
    
    # Step 1: Prepare
    print("[1/3] Preparing CSV files...")
    prepare_csvs(input_dir, output_dir)
    
    # Step 2: Generate
    print("\n[2/3] Generating playlists...")
    params = build_params_from_args(args)
    generate_playlists(output_dir, participant_id, params, preview=False)
    
    # Step 3: Analyse
    print("\n[3/3] Analysing playlists...")
    analyse_playlists(output_dir, participant_id, not args.no_viz)
    
    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60 + "\n")


# ============================================================
# ARGUMENT PARSING
# ============================================================

def add_common_arguments(parser):
    """Add arguments common to multiple commands"""
    parser.add_argument(
        'codename',
        type=str,
        help='Participant codename (e.g., aardbei, bosbes, peer)'
    )


def add_participant_argument(parser):
    """Add participant ID argument (optional, defaults to codename)"""
    parser.add_argument(
        '-p', '--participant',
        type=str,
        default=None,
        help='Participant ID (defaults to codename if not specified)'
    )


def add_playlist_parameters(parser, show_help='basic'):
    """
    Add playlist parameter arguments
    
    Args:
        parser: Argument parser
        show_help: 'basic' (hide in main help) or 'full' (show in --help-full)
    """
    help_text = argparse.SUPPRESS if show_help == 'basic' else None
    
    # Get defaults from DEFAULT_PARAMS
    calm_defaults = DEFAULT_PARAMS['calm']
    neutral_defaults = DEFAULT_PARAMS['neutral']
    energy_defaults = DEFAULT_PARAMS['energy']
    
    # Calm playlist parameters
    calm_group = parser.add_argument_group('calm playlist (advanced tuning)')
    calm_group.add_argument('--calm-tempo-min', type=int, default=calm_defaults['min_tempo'], 
                           help=help_text or f"Min BPM (default: {calm_defaults['min_tempo']})")
    calm_group.add_argument('--calm-tempo-max', type=int, default=calm_defaults['max_tempo'], 
                           help=help_text or f"Max BPM (default: {calm_defaults['max_tempo']})")
    calm_group.add_argument('--calm-energy-max', type=float, default=calm_defaults['max_energy'], 
                           help=help_text or f"Max energy (default: {calm_defaults['max_energy']})")
    
    # Neutral playlist parameters
    neutral_group = parser.add_argument_group('neutral playlist (advanced tuning)')
    neutral_group.add_argument('--neutral-tempo-min', type=int, default=neutral_defaults['min_tempo'], 
                              help=help_text or f"Min BPM (default: {neutral_defaults['min_tempo']})")
    neutral_group.add_argument('--neutral-tempo-max', type=int, default=neutral_defaults['max_tempo'], 
                              help=help_text or f"Max BPM (default: {neutral_defaults['max_tempo']})")
    neutral_group.add_argument('--neutral-energy-min', type=float, default=neutral_defaults['min_energy'], 
                              help=help_text or f"Min energy (default: {neutral_defaults['min_energy']})")
    neutral_group.add_argument('--neutral-energy-max', type=float, default=neutral_defaults['max_energy'], 
                              help=help_text or f"Max energy (default: {neutral_defaults['max_energy']})")
    
    # energy playlist parameters
    energy_group = parser.add_argument_group('energy playlist (advanced tuning)')
    energy_group.add_argument('--energy-tempo-min', type=int, default=energy_defaults['min_tempo'], 
                             help=help_text or f"Min BPM (default: {energy_defaults['min_tempo']})")
    energy_group.add_argument('--energy-tempo-max', type=int, default=energy_defaults['max_tempo'], 
                             help=help_text or f"Max BPM (default: {energy_defaults['max_tempo']})")
    energy_group.add_argument('--energy-energy-min', type=float, default=energy_defaults['min_energy'], 
                             help=help_text or f"Min energy (default: {energy_defaults['min_energy']})")


def create_parser():
    """
    Create argument parser with all commands and options
    
    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description='Spotify Playlist Generator - Create calm, neutral, and energy playlists',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Quick start - process everything for participant 'aardbei'
  spotify_cli.py all aardbei
  
  # Preview what would happen (dry run)
  spotify_cli.py all aardbei --dry-run
  
  # Skip visualizations (faster)
  spotify_cli.py all aardbei --no-viz
  
  # Fine-tune calm playlist tempo
  spotify_cli.py all aardbei --calm-tempo-max 95
  
  # Individual steps (if you need more control)
  spotify_cli.py prepare aardbei
  spotify_cli.py generate aardbei
  spotify_cli.py analyse aardbei

GETTING HELP:
  spotify_cli.py --help          Show this help
  spotify_cli.py --help-full     Show all advanced options
  spotify_cli.py [command] -h    Show help for specific command

FOLDER STRUCTURE:
  data/playlists/aardbei/*.csv                    Input CSVs (from Exportify)
  data/playlists/aardbei/playlists_generated/     Output playlists + analysis
        """
    )
    
    # Check for --help-full flag
    if '--help-full' in sys.argv:
        # Show full help by removing the flag and letting normal help run
        sys.argv.remove('--help-full')
        show_advanced = True
    else:
        show_advanced = False
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # ========== PREPARE COMMAND ==========
    prepare_parser = subparsers.add_parser(
        'prepare',
        help='Combine and clean CSV files from Spotify Exportify'
    )
    add_common_arguments(prepare_parser)
    
    # ========== GENERATE COMMAND ==========
    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate calm, neutral, and energy playlists'
    )
    add_common_arguments(generate_parser)
    add_participant_argument(generate_parser)
    add_playlist_parameters(generate_parser, 'full' if show_advanced else 'basic')
    generate_parser.add_argument('--preview', action='store_true', help='Show detailed song lists')
    
    # ========== ANALYSE COMMAND ==========
    analyse_parser = subparsers.add_parser(
        'analyse',
        help='Analyse and visualise generated playlists'
    )
    add_common_arguments(analyse_parser)
    add_participant_argument(analyse_parser)
    analyse_parser.add_argument('--no-viz', action='store_true', help='Skip visualization generation')
    
    # ========== ALL COMMAND ==========
    all_parser = subparsers.add_parser(
        'all',
        help='Run complete workflow: prepare -> generate -> analyse'
    )
    add_common_arguments(all_parser)
    add_participant_argument(all_parser)
    add_playlist_parameters(all_parser, 'full' if show_advanced else 'basic')
    all_parser.add_argument('--no-viz', action='store_true', help='Skip visualization generation')
    all_parser.add_argument('--dry-run', action='store_true', help='Preview what would happen without making changes')
    
    return parser


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Execute the requested command
    try:
        if args.command == 'prepare':
            execute_prepare(args)
        
        elif args.command == 'generate':
            execute_generate(args)
        
        elif args.command == 'analyse':
            execute_analyse(args)
        
        elif args.command == 'all':
            execute_all(args)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...\n", file=sys.stderr)
        sys.exit(130)
    
    except Exception as e:
        print(f"\nERROR: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()