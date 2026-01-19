#!/usr/bin/env python3
"""
Interactive TUI for Spotify Playlist Manager
Navigate with arrow keys, select with Enter
"""

import questionary
from questionary import Style
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

# Custom style
custom_style = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#f44336 bold'),
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#cc5454'),
    ('separator', 'fg:#cc5454'),
    ('instruction', ''),
    ('text', ''),
])


def clear_screen():
    """Clear the terminal screen"""
    subprocess.run(['clear'] if sys.platform != 'win32' else ['cls'], shell=True)


def show_header():
    """Display app header"""
    console.print(Panel.fit(
        "[bold cyan]🎵 Spotify Playlist Manager[/bold cyan]\n"
        "[dim]Music & Biometrics Research Project[/dim]",
        border_style="cyan"
    ))


def get_participants():
    """Get list of participants from data directory"""
    data_dir = Path("data/playlists")
    if data_dir.exists():
        return [p.name for p in data_dir.iterdir() if p.is_dir() and not p.name.startswith('.')]
    return []


def run_command(cmd):
    """Execute CLI command and show output"""
    console.print(f"\n[dim]Running: {' '.join(cmd)}[/dim]\n")
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        console.print("\n[bold red]❌ Command failed[/bold red]")
    else:
        console.print("\n[bold green]✓ Done![/bold green]")
    
    input("\nPress Enter to continue...")


def generate_playlists_menu():
    """Generate playlists submenu"""
    clear_screen()
    show_header()
    
    # Get available participants
    participants = get_participants()
    
    if not participants:
        console.print("[yellow]⚠️  No participants found in data/playlists/[/yellow]")
        console.print("[dim]Add participant folders first[/dim]\n")
        input("Press Enter to continue...")
        return
    
    # Ask for participant
    participant = questionary.select(
        "Select participant:",
        choices=participants + ["← Back"],
        style=custom_style
    ).ask()
    
    if participant == "← Back" or not participant:
        return
    
    # Ask for playlist type
    playlist_type = questionary.select(
        "Select playlist type:",
        choices=[
            "All playlists (calm + neutral + upbeat)",
            "Calm only",
            "Neutral only", 
            "Upbeat only",
            "← Back"
        ],
        style=custom_style
    ).ask()
    
    if playlist_type == "← Back" or not playlist_type:
        return
    
    # Build command
    if playlist_type.startswith("All"):
        cmd = ["python", "scripts/playlists/spotify_cli.py", "all", participant]
    else:
        type_map = {
            "Calm only": "calm",
            "Neutral only": "neutral",
            "Upbeat only": "upbeat"
        }
        playlist = type_map[playlist_type]
        cmd = ["python", "scripts/playlists/spotify_cli.py", "generate", participant, f"--type={playlist}"]
    
    run_command(cmd)


def outlier_detection_menu():
    """Outlier detection submenu"""
    clear_screen()
    show_header()
    
    # Get participants
    participants = get_participants()
    
    if not participants:
        console.print("[yellow]⚠️  No participants found[/yellow]\n")
        input("Press Enter to continue...")
        return
    
    participant = questionary.select(
        "Select participant:",
        choices=participants + ["← Back"],
        style=custom_style
    ).ask()
    
    if participant == "← Back" or not participant:
        return
    
    playlist_type = questionary.select(
        "Select playlist type:",
        choices=["calm", "neutral", "upbeat", "← Back"],
        style=custom_style
    ).ask()
    
    if playlist_type == "← Back" or not playlist_type:
        return
    
    # Build path
    playlist_path = f"data/playlists/{participant}/playlists_generated/{participant}_{playlist_type}_playlist.csv"
    
    # Check if file exists
    if not Path(playlist_path).exists():
        console.print(f"\n[bold red]❌ Playlist not found:[/bold red] {playlist_path}")
        console.print("[dim]Generate the playlist first[/dim]\n")
        input("Press Enter to continue...")
        return
    
    cmd = [
        "python", 
        "scripts/playlists/outlier_detection.py",
        "--playlist", playlist_path,
        "--type", playlist_type
    ]
    
    run_command(cmd)


def validate_playlist_menu():
    """Validate playlist submenu"""
    clear_screen()
    show_header()
    
    participants = get_participants()
    
    if not participants:
        console.print("[yellow]⚠️  No participants found[/yellow]\n")
        input("Press Enter to continue...")
        return
    
    participant = questionary.select(
        "Select participant:",
        choices=participants + ["← Back"],
        style=custom_style
    ).ask()
    
    if participant == "← Back" or not participant:
        return
    
    playlist_type = questionary.select(
        "Select playlist type:",
        choices=["calm", "neutral", "upbeat", "← Back"],
        style=custom_style
    ).ask()
    
    if playlist_type == "← Back" or not playlist_type:
        return
    
    cmd = [
        "python",
        "scripts/playlists/spotify_cli.py",
        "validate",
        participant,
        f"--type={playlist_type}"
    ]
    
    run_command(cmd)


def view_stats_menu():
    """View statistics submenu"""
    clear_screen()
    show_header()
    
    participants = get_participants()
    
    if not participants:
        console.print("[yellow]⚠️  No participants found[/yellow]\n")
        input("Press Enter to continue...")
        return
    
    participant = questionary.select(
        "Select participant:",
        choices=participants + ["← Back"],
        style=custom_style
    ).ask()
    
    if participant == "← Back" or not participant:
        return
    
    cmd = ["python", "scripts/playlists/spotify_cli.py", "stats", participant]
    run_command(cmd)


def main_menu():
    """Main application menu"""
    while True:
        clear_screen()
        show_header()
        
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "🎵 Generate playlists",
                "🔍 Run outlier detection",
                "✓ Validate playlist",
                "📊 View statistics",
                "❌ Exit"
            ],
            style=custom_style
        ).ask()
        
        if not choice or choice == "❌ Exit":
            clear_screen()
            console.print("[bold cyan]👋 Goodbye![/bold cyan]\n")
            break
        
        if choice == "🎵 Generate playlists":
            generate_playlists_menu()
        elif choice == "🔍 Run outlier detection":
            outlier_detection_menu()
        elif choice == "✓ Validate playlist":
            validate_playlist_menu()
        elif choice == "📊 View statistics":
            view_stats_menu()


def main():
    """Entry point"""
    try:
        main_menu()
    except KeyboardInterrupt:
        clear_screen()
        console.print("\n[bold cyan]👋 Goodbye![/bold cyan]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
