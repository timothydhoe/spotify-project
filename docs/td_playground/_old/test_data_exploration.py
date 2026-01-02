import json
import pandas as pd
# from datetime import datetime
# import numpy as np

# Load the key datasets
def load_data():
    """Load and preview the most valuable datasets"""
    
    # 1. Daily Summary - richest dataset (98 days)
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Aggregator/UDSFile_2025-03-31_2025-07-09.json') as f:
        uds = pd.DataFrame(json.load(f))
    
    # 2. Sleep Data (98 nights)
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Wellness/2025-07-10_2025-10-18_119277684_sleepData.json') as f:
        sleep = pd.DataFrame(json.load(f))
    
    # 3. Fitness Age progression (582 records)
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Wellness/119277684_fitnessAgeData.json') as f:
        fitness_age = pd.DataFrame(json.load(f))
    
    # 4. Biometrics/Weight (486 measurements)
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Wellness/119277684_userBioMetrics.json') as f:
        biometrics = pd.DataFrame(json.load(f))
    
    # 7. VO2 Max progression (8 measurements)
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Metrics/MetricsMaxMetData_20250828_20251206_119277684.json') as f:
        vo2_max = pd.DataFrame(json.load(f))
    
    # 8. Hydration (72 logs)
    with open('data/Garmin_data/DI_CONNECT/DI-Connect-Aggregator/HydrationLogFile_2025-07-05_2025-10-13.json') as f:
        hydration = pd.DataFrame(json.load(f))
    
    return {
        'daily_summary': uds,
        'sleep': sleep,
        'fitness_age': fitness_age,
        'biometrics': biometrics,
        'vo2_max': vo2_max,
        'hydration': hydration
    }

def analyze_data_potential(data):
    """Identify what's useful and why"""
    
    print("=" * 80)
    print("DATA QUALITY & POTENTIAL USE CASES")
    print("=" * 80)
    
    # 1. DAILY ACTIVITY METRICS
    uds = data['daily_summary']
    print("\n1. DAILY ACTIVITY METRICS (UDS)")
    print(f"   Records: {len(uds)} days")
    print(f"   Date range: {uds['calendarDate'].min()} to {uds['calendarDate'].max()}")
    print("\n   Key metrics available:")
    print("   - Steps, distance, floors")
    print("   - Calories (active, BMR, wellness)")
    print("   - Heart rate (min, max, resting, avg)")
    print("   - Stress levels (allDayStress)")
    print("   - Body Battery")
    print("   - Intensity minutes (moderate/vigorous)")
    print("   - Respiration rate")
    print("\n   WHY USEFUL: Core daily activity + recovery metrics. Body Battery & stress")
    print("               correlation with activity could show overtraining patterns.")
    
    # 2. SLEEP DATA
    sleep = data['sleep']
    print("\n2. SLEEP DATA")
    print(f"   Records: {len(sleep)} nights")
    print("\n   Key metrics:")
    print("   - Sleep stages (deep, light, REM, awake)")
    print("   - Respiration during sleep")
    print("   - Sleep stress")
    print("   - Restless moments")
    print("\n   WHY USEFUL: Sleep quality metrics. Can correlate with activity intensity,")
    
    # 3. FITNESS AGE
    fa = data['fitness_age']
    print("\n3. FITNESS AGE PROGRESSION")
    print(f"   Records: {len(fa)} measurements")
    print("\n   Tracks:")
    print("   - Biological age vs chronological age")
    print("   - VO2 max trends")
    print("   - BMI, RHR, activity levels")
    print("\n   WHY USEFUL: Long-term fitness improvement tracking. Shows actual health")
    print("               improvements beyond just activity counts.")
    
    # 4. VO2 MAX
    vo2 = data['vo2_max']
    print("\n5. VO2 MAX PROGRESSION")
    print(f"   Measurements: {len(vo2)}")
    if len(vo2) > 0:
        print(f"   Range: {vo2['vo2MaxValue'].min()} → {vo2['vo2MaxValue'].max()}")
    print("\n   WHY USEFUL: Cardiorespiratory fitness benchmark. Shows training effectiveness.")
    
    # 5. BIOMETRICS
    bio = data['biometrics']
    print("\n6. WEIGHT/BIOMETRICS")
    print(f"   Records: {len(bio)} measurements")
    print("\n   WHY USEFUL: Weight trends correlate with activity/nutrition changes.")

def show_correlation_opportunities(data):
    """Show what can be cross-analyzed"""
    
    print("\n" + "=" * 80)
    print("KEY CORRELATION OPPORTUNITIES")
    print("=" * 80)
    
    
    print("\n2. RECOVERY × ACTIVITY")
    print("   - Body Battery depletion vs intensity minutes")
    print("   - Sleep quality after high-intensity days")
    print("   - Resting HR trends with training load")
    
    print("\n3. FITNESS PROGRESSION")
    print("   - VO2 max improvement vs training volume")
    print("   - Fitness age reduction over time")
    print("   - Weight changes vs activity patterns")
    
    print("\n4. STRESS & RECOVERY")
    print("   - All-day stress vs sleep quality")
    print("   - Body Battery recovery rate")
    print("   - Respiration rate patterns during stress/recovery")

def extract_sample_insights(data):
    """Show how to actually extract useful info"""
    
    print("\n" + "=" * 80)
    print("SAMPLE DATA EXTRACTION")
    print("=" * 80)
    
    # Example 1: Daily metrics with dates
    uds = data['daily_summary'].copy()
    uds['date'] = pd.to_datetime(uds['calendarDate'])
    
    print("\nDaily Activity Summary:")
    print(uds[['date', 'totalSteps', 'restingHeartRate', 'bodyBattery', 'allDayStress']].head())
    
    # Example 2: Sleep summary
    sleep = data['sleep'].copy()
    sleep['date'] = pd.to_datetime(sleep['calendarDate'])
    sleep['total_sleep_hrs'] = (sleep['deepSleepSeconds'] + sleep['lightSleepSeconds'] + 
                                 sleep['remSleepSeconds']) / 3600
    
    print("\nSleep Summary:")
    print(sleep[['date', 'total_sleep_hrs', 'deepSleepSeconds', 'avgSleepStress']].head())
    
    # Example 3: VO2 Max trend
    vo2 = data['vo2_max'].copy()
    if len(vo2) > 0:
        vo2['date'] = pd.to_datetime(vo2['calendarDate'])
        print("\nVO2 Max Progression:")
        print(vo2[['date', 'vo2MaxValue', 'maxMet']].sort_values('date'))
    

if __name__ == "__main__":
    print("Loading data...")
    data = load_data()
    
    analyze_data_potential(data)
    show_correlation_opportunities(data)
    extract_sample_insights(data)
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print("""
The most valuable datasets for analysis are:
1. UDS (daily summary) - complete activity/stress/recovery picture
2. Sleep data - recovery quality metrics
4. Fitness age - long-term progress tracking

Next steps:
- Merge datasets on calendarDate for multi-variate analysis
- Calculate rolling averages for trend analysis
- Build correlation matrices between key metrics
""")