import json
import pandas as pd
# import numpy as np
from datetime import timedelta

def load_and_merge_data():
    """
    Merge key datasets on calendarDate for multi-variate analysis
    WHY: Single dataframe enables correlation analysis across metrics
    """
    
    # Load daily summary (richest dataset)
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Aggregator/UDSFile_2025-07-09_2025-10-17.json') as f:
        uds = pd.DataFrame(json.load(f))
    uds['date'] = pd.to_datetime(uds['calendarDate'])
    
    # Extract key metrics from nested structures
    # Body battery is nested - extract if available
    uds['body_battery_charged'] = uds['bodyBattery'].apply(
        lambda x: x.get('bodyBatteryMostRecentValue') if isinstance(x, dict) else None
    )
    uds['avg_stress'] = uds['allDayStress'].apply(
        lambda x: x.get('averageStressLevel') if isinstance(x, dict) else None
    )
    
    # Load sleep data
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Wellness/2025-04-01_2025-07-10_119277684_sleepData.json') as f:
        sleep = pd.DataFrame(json.load(f))
    sleep['date'] = pd.to_datetime(sleep['calendarDate'])
    
    # Calculate useful sleep metrics
    sleep['total_sleep_hrs'] = (
        sleep['deepSleepSeconds'] + sleep['lightSleepSeconds'] + sleep['remSleepSeconds']
    ) / 3600
    sleep['deep_sleep_pct'] = (sleep['deepSleepSeconds'] / 
                               (sleep['deepSleepSeconds'] + sleep['lightSleepSeconds'] + 
                                sleep['remSleepSeconds']) * 100)
    
    # Merge
    df = uds.merge(
        sleep[['date', 'total_sleep_hrs', 'deep_sleep_pct', 'avgSleepStress']], 
        on='date', 
        how='left',
        suffixes=('', '_sleep')
    )
    
    # Add menstrual cycle phase
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Wellness/119277684_MenstrualCycles.json') as f:
        cycles = pd.DataFrame(json.load(f))
    
    df = add_cycle_phase(df, cycles)
    
    return df

def add_cycle_phase(df, cycles):
    """
    Add menstrual cycle phase to daily data
    WHY: Enables analysis of performance/recovery by hormonal phase
    """
    
    df['cycle_phase'] = None
    df['days_since_period_start'] = None
    
    for _, cycle in cycles.iterrows():
        if pd.isna(cycle.get('actualCycleLength')):
            continue
            
        start = pd.to_datetime(cycle['startDate'])
        cycle_length = int(cycle['actualCycleLength'])
        end = start + timedelta(days=cycle_length)
        
        # Define phases (simplified)
        # Menstrual: days 1-5
        # Follicular: days 6-13
        # Ovulatory: days 14-16
        # Luteal: days 17-end
        
        mask = (df['date'] >= start) & (df['date'] < end)
        days_since = (df.loc[mask, 'date'] - start).dt.days + 1
        df.loc[mask, 'days_since_period_start'] = days_since
        
        df.loc[mask & (days_since <= 5), 'cycle_phase'] = 'menstrual'
        df.loc[mask & (days_since > 5) & (days_since <= 13), 'cycle_phase'] = 'follicular'
        df.loc[mask & (days_since > 13) & (days_since <= 16), 'cycle_phase'] = 'ovulatory'
        df.loc[mask & (days_since > 16), 'cycle_phase'] = 'luteal'
    
    return df

def analyze_recovery_patterns(df):
    """
    Example analysis: Recovery quality by training load
    WHY: Identifies if training volume is impacting recovery negatively
    """
    
    print("=" * 80)
    print("RECOVERY ANALYSIS")
    print("=" * 80)
    
    # Create intensity categories
    df['intensity_category'] = pd.cut(
        df['vigorousIntensityMinutes'], 
        bins=[0, 10, 30, 100],
        labels=['Low', 'Medium', 'High']
    )
    
    # Group by intensity and look at recovery metrics
    recovery = df.groupby('intensity_category').agg({
        'total_sleep_hrs': 'mean',
        'deep_sleep_pct': 'mean',
        'restingHeartRate': 'mean',
        'body_battery_charged': 'mean',
        'avg_stress': 'mean'
    }).round(2)
    
    print("\nRecovery Metrics by Training Intensity:")
    print(recovery)
    print("\nInterpretation:")
    print("- Higher RHR on high-intensity days = normal acute response")
    print("- Lower deep sleep % on high-intensity = potential overtraining signal")
    print("- Lower body battery = recovery debt accumulating")



def identify_trends(df):
    """
    Example analysis: Longitudinal trends
    WHY: Show if fitness is improving over time
    """
    
    print("\n" + "=" * 80)
    print("TREND ANALYSIS")
    print("=" * 80)
    
    # Calculate 7-day rolling averages to smooth noise
    df_sorted = df.sort_values('date')
    df_sorted['rhr_7day'] = df_sorted['restingHeartRate'].rolling(window=7, min_periods=1).mean()
    df_sorted['steps_7day'] = df_sorted['totalSteps'].rolling(window=7, min_periods=1).mean()
    df_sorted['stress_7day'] = df_sorted['avg_stress'].rolling(window=7, min_periods=1).mean()
    
    # Compare first vs last month
    first_month = df_sorted.head(30)
    last_month = df_sorted.tail(30)
    
    print("\nFirst Month vs Last Month (7-day rolling avg):")
    print(f"RHR:    {first_month['rhr_7day'].mean():.1f} → {last_month['rhr_7day'].mean():.1f} bpm")
    print(f"Steps:  {first_month['steps_7day'].mean():.0f} → {last_month['steps_7day'].mean():.0f}")
    print(f"Stress: {first_month['stress_7day'].mean():.1f} → {last_month['stress_7day'].mean():.1f}")
    
    print("\nInterpretation:")
    print("- Decreasing RHR = improving cardiovascular fitness")
    print("- Increasing steps = activity level improving")
    print("- Stress trends = workload/recovery balance")

def calculate_correlations(df):
    """
    Example analysis: What metrics move together?
    WHY: Identify leading indicators (e.g., RHR predicts burnout)
    """
    
    print("\n" + "=" * 80)
    print("CORRELATION ANALYSIS")
    print("=" * 80)
    
    # Select numeric columns of interest
    correlation_cols = [
        'totalSteps', 'vigorousIntensityMinutes', 'restingHeartRate',
        'body_battery_charged', 'avg_stress', 'total_sleep_hrs', 'deep_sleep_pct'
    ]
    
    # Filter to available columns
    available_cols = [c for c in correlation_cols if c in df.columns]
    corr_matrix = df[available_cols].corr().round(2)
    
    print("\nCorrelation Matrix:")
    print(corr_matrix)
    
    print("\nKey insights to look for:")
    print("- High RHR + high stress = overtraining risk")
    print("- Low body battery + low sleep = recovery deficit")
    print("- Steps vs vigorous minutes = training balance")

if __name__ == "__main__":
    print("Loading and merging datasets...")
    df = load_and_merge_data()
    
    print(f"\nMerged dataset: {len(df)} days")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"\nColumns: {df.shape[1]}")
    
    # Run analyses
    analyze_recovery_patterns(df)
    identify_trends(df)
    calculate_correlations(df)
    
    print("\n" + "=" * 80)
    print("EXPORT OPTIONS")
    print("=" * 80)
    print("\n# Save merged dataset for further analysis:")
    print("df.to_csv('merged_fitness_data.csv', index=False)")
    print("\n# Save cycle phase analysis:")
    print("cycle_df = df[df['cycle_phase'].notna()]")
    print("cycle_df.to_csv('cycle_annotated_data.csv', index=False)")