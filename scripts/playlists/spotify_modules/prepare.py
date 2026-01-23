"""
file: prepare.py
----------------
Clean and combine Exportify CSV files

WHAT THIS MODULE DOES:
1. Finds all CSV files exported from Spotify (via Exportify)
2. Reads and combines them into one dataset
3. Standardises column names for consistency
4. Removes duplicate songs
5. Saves the cleaned data for playlist generation
"""

import pandas as pd
from pathlib import Path


# ============================================================
# CONFIGURATION: Column Name Standardisation
# ============================================================

# Exportify uses verbose names like "Track Name" and "Artist Name(s)"
# We standardise them to shorter, cleaner names for easier processing
COLUMN_MAPPING = {
    'Track Name': 'name',
    'Artist Name(s)': 'artists',
    'Album Name': 'album',
    'Duration (ms)': 'duration_ms',
    'Tempo': 'tempo',
    'Energy': 'energy',
    'Valence': 'valence',
    'Acousticness': 'acousticness',
    'Danceability': 'danceability',
    'Loudness': 'loudness',
    'Speechiness': 'speechiness',
    'Instrumentalness': 'instrumentalness',
    'Liveness': 'liveness',
    'Key': 'key',
    'Mode': 'mode',
    'Time Signature': 'time_signature',
    'Track URI': 'uri'
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def find_csv_files(directory):
    """
    Find all CSV files in the participant's folder
    
    Args:
        directory: Path to folder containing participant CSV files
        
    Returns:
        List of CSV file paths
    """
    directory = Path(directory)
    
    if not directory.exists():
        raise FileNotFoundError(f"Input folder not found: {directory}")
    
    # Find only CSV files in the main directory (not subdirectories)
    csv_files = [f for f in directory.glob("*.csv") if f.is_file()]
    
    if not csv_files:
        raise ValueError(f"No CSV files found in {directory}")
    
    return csv_files


def read_and_combine_csvs(csv_files):
    """
    Read all CSV files and combine into one dataframe
    
    Args:
        csv_files: List of CSV file paths
        
    Returns:
        Combined pandas DataFrame
    """
    print(f"\nFound {len(csv_files)} CSV file(s):")
    
    dataframes = []
    for csv_file in csv_files:
        print(f"  - {csv_file.name}")
        try:
            df = pd.read_csv(csv_file)
            dataframes.append(df)
        except Exception as e:
            print(f"    Warning: Could not read {csv_file.name}: {e}")
            continue
    
    if not dataframes:
        raise ValueError("No valid CSV files could be read")
    
    # Combine all into single dataframe
    combined = pd.concat(dataframes, ignore_index=True)
    
    return combined


def standardise_columns(df, column_mapping):
    """
    Rename columns from Exportify format to our internal format
    
    Args:
        df: DataFrame with Exportify column names
        column_mapping: Dictionary mapping old names to new names
        
    Returns:
        DataFrame with standardised column names
    """
    # Only rename columns that actually exist in the dataframe
    existing_mappings = {
        old: new 
        for old, new in column_mapping.items() 
        if old in df.columns
    }
    
    df = df.rename(columns=existing_mappings)
    
    # Sort columns alphabetically for consistency
    df = df.sort_index(axis=1)
    
    return df


def remove_duplicates(df):
    """
    Remove duplicate songs based on Spotify Track URI
    
    Args:
        df: DataFrame with potential duplicates
        
    Returns:
        DataFrame with duplicates removed
    """
    original_count = len(df)
    
    if 'uri' in df.columns:
        df = df.drop_duplicates(subset=['uri'], keep='first')
        duplicates_removed = original_count - len(df)
        
        if duplicates_removed > 0:
            print(f"  Removed {duplicates_removed} duplicate track(s)")
    
    return df


def save_combined_file(df, output_dir):
    """
    Save the cleaned, combined data to output directory
    
    Args:
        df: Cleaned DataFrame
        output_dir: Path to playlists_generated folder
        
    Returns:
        Path to saved file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / 'combined.csv'
    df.to_csv(output_path, index=False)
    
    return output_path


def filter_unsuitable_songs(df):
    """
    Remove songs unsuitable for therpeutic playlists

    FILTERS:
    - Speechiness > 0.7: Too much talking (podcasts, spoken word, ...)
    - Liveness > 0.8: Live recordings with audience noise

    These features interfere with music therapy effectiveness

    Args:
        df: DataFrame with potential unsuitable songs

    Returns:
        Dataframe with unsuitable songs removed
    """
    orginal_count = len(df)

    if 'speechiness' in df.columns:
        before = len(df)
        df = df[df['speechiness'] <= 0.7]
        if len(df) < before:
            print(f"  Removed {before - len(df)} speechy track(s) (speechiness > 0.7)")

    if 'liveness' in df.columns:
        before = len(df)
        df = df[df['liveness'] <= 0.8]
        if len(df) < before:
            print(f"  Removed {before - len(df)} live recording (liveness > 0.0)")

    total_removed = orginal_count - len(df)
    if total_removed > 0:
        print(f"  Total unsuitable tracks removed: {total_removed}")
    
    return df


# ============================================================
# MAIN FUNCTION
# ============================================================

def prepare_csvs(input_dir, output_dir):
    """
    Clean and combine all CSV files from Exportify
    
    This is the main entry point that orchestrates the entire preparation process.
    
    WORKFLOW:
    1. Find all CSV files in participant folder
    2. Read and combine them
    3. Standardise column names
    4. Remove duplicate songs
    6. Filter unsuitable songs (speechiness and liveness)
    5. Save to output directory
    
    Args:
        input_dir: Path to folder containing participant CSV files
        output_dir: Path to playlists_generated folder (will be created)
        
    Returns:
        Path to combined CSV file
    """
    print(f"Output directory: {output_dir}")
    
    # Step 1: Find CSV files
    csv_files = find_csv_files(input_dir)
    
    # Step 2: Read and combine
    combined_df = read_and_combine_csvs(csv_files)
    
    # Step 3: Standardise column names
    combined_df = standardise_columns(combined_df, COLUMN_MAPPING)
    
    # Step 4: Remove duplicates
    combined_df = remove_duplicates(combined_df)

    # Step 5: Filter Unsuitable songs
    combined_df = filter_unsuitable_songs(combined_df)
    # print("TEST")

    # Step 6: Save to output
    output_path = save_combined_file(combined_df, output_dir)
    
    # Summary
    print(f"\nCombined {len(csv_files)} file(s) -> {len(combined_df)} unique tracks")
    print(f"Saved to: {output_path}")
    
    return output_path