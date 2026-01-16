# prepare_exportify.py
import pandas as pd

# Read the file of the candidate. TO BE ADAPTED FOR EACH CSV. 
# df = pd.read_csv('participant_PXXX_playlist.csv')
df = pd.read_csv('/Users/timothydhoe/Code/spotify-project/docs/td_playground/testdata/bosbes/Evelien_Viroux.csv')


df = df.rename(columns={
    'Track Name': 'name',
    'Artist Name(s)': 'artists',
    'Tempo': 'tempo',
    'Energy': 'energy',
    'Loudness': 'loudness',
    'Valence': 'valence',
    'Acousticness': 'acousticness',
    'Danceability': 'danceability',
    'Duration (ms)': 'duration_ms'
})

# Save the file -- CHANGE CANDIDATE CODE FOR EACH OUTPUT.
df.to_csv('testdata/matched_P001.csv', index=False)
print(f"✓ Prepared {len(df)} songs for playlist generation")