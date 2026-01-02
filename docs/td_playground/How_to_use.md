# How to use

## Participants export their playlists

1. Go to https://exportify.net
2. Log in with Spotify
3. Export at least 3 playlists of their choice → 'Download CSV'
4. Email the CSV file(s)


## For us

#### Preparing the CSV files and folders.

1. Create folder named after participant code
2. Drop CSV files in there.


#### Combine_playlists.py

Run this file to concatenate all csv files.


#### prepare_exportify.py

Run this file to prepare the CSV to be read by the playlist generator.
(not sure this'll be needed in the future...)

```bash
python prepare_exportify.py
```


#### Playlist_generator

Run this file, for each candidate, to generate two bespoke playlists

example usage:
```bash
python playlist_generator.py --input matched_P001.csv --participant P001 --preview
```