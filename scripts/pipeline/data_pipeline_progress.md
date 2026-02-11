# Data Pipeline Progress

## Current Status: 🏗️ Foundation Built

### Completed
- [x] Project structure defined (bronze/silver/gold)
- [x] Config file with paths and constants
- [x] Module stubs created (parse_data, clean, extract_windows)
- [x] Main pipeline orchestrator

### In Progress
- [ ] Obtain FIT files from Garmin vivoactive 5
- [ ] Obtain check-in data from Google Forms

### Next Steps
1. Implement `load_fit_files()` once FIT files available
2. Implement `load_checkins()` once Forms data ready
3. Test on single participant/event
4. Implement basic cleaning functions
5. Implement window extraction logic

### Future Features (after core works)
- Outlier detection (physiological bounds)
- Gap detection in smartwatch data
- Resampling to consistent time intervals
- Spotify feature extraction
- ML feature engineering