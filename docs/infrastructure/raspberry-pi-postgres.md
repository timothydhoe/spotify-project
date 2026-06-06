# Raspberry Pi PostgreSQL — Architecture Design
> Project R.E.M. · Infrastructure concept (design only, not yet implemented)
> Date: 2026-05-26

---

## Why This Would Help

Currently all participant data lives in per-participant CSV files scattered across
`data/playlists/`, `data/wearables/`, `data/checkins/`, and `data/analysis/`.
This makes cross-participant queries impossible and forces the Shiny app to load
everything into memory at startup.

A centralised PostgreSQL database on a Raspberry Pi would enable:

1. **Cross-participant playlist generation** — find songs that worked well for
   participants with similar biometric profiles.
2. **Real-time session logging** — replace Google Forms check-ins with a proper
   REST API. No more CSV appends.
3. **Remote access via HTTPS** — open the Shiny app from anywhere without a
   local Python environment.
4. **Persistent storage** — data survives app restarts; no loading 40+ CSV files
   at startup.

---

## Architecture Overview

```
Internet
   │
   ▼
Caddy (reverse proxy, HTTPS via Let's Encrypt)
   │
   ├──► Shiny for Python app  (port 8000)
   └──► pgAdmin web UI        (port 5050)
          │
          ▼
   PostgreSQL 16  (port 5432, internal only)
          │
   pg_data volume (persistent Docker volume)
```

SSH tunnel for direct psql access:
```
ssh -L 5432:localhost:5432 pi@<raspberry-pi-ip>
psql -h localhost -U rem_user -d moodtune
```

---

## Docker Compose

```yaml
# docker-compose.yml — deploy on Raspberry Pi
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB:       moodtune
      POSTGRES_USER:     rem_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "127.0.0.1:5432:5432"   # localhost only — Caddy/SSH handle external

  pgadmin:
    image: dpage/pgadmin4:latest
    restart: always
    environment:
      PGADMIN_DEFAULT_EMAIL:    admin@rem.local
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
    ports:
      - "127.0.0.1:5050:80"
    depends_on:
      - postgres

  shiny:
    build: .
    restart: always
    environment:
      DATABASE_URL: postgresql://rem_user:${POSTGRES_PASSWORD}@postgres:5432/moodtune
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      - postgres
    command: ["uv", "run", "shiny", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]

  caddy:
    image: caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - shiny
      - pgadmin

volumes:
  pg_data:
  caddy_data:
  caddy_config:
```

`.env` file (never commit):
```
POSTGRES_PASSWORD=<strong-password>
PGADMIN_PASSWORD=<strong-password>
```

**Caddyfile** (replace `rem.yourdomain.be` with your domain):
```
rem.yourdomain.be {
    reverse_proxy shiny:8000
}

pgadmin.yourdomain.be {
    reverse_proxy pgadmin:80
}
```

---

## Database Schema

```sql
-- init.sql — run once at container startup

CREATE TABLE participants (
    id          SERIAL PRIMARY KEY,
    codename    VARCHAR(50) UNIQUE NOT NULL,
    device_type VARCHAR(20),             -- 'garmin' | 'huawei'
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sessions (
    id                  SERIAL PRIMARY KEY,
    participant_id      INTEGER REFERENCES participants(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    playlist_type       VARCHAR(10) NOT NULL CHECK (playlist_type IN ('Calm','Neutral','Energy')),
    start_local         TIME,
    duration_min        FLOAT,
    mood_before         VARCHAR(100),
    mood_before_score   SMALLINT CHECK (mood_before_score BETWEEN 1 AND 10),
    mood_after          VARCHAR(100),
    mood_after_score    SMALLINT CHECK (mood_after_score BETWEEN 1 AND 10),
    pre_stress_mean     FLOAT,
    stress_mean         FLOAT,
    post_stress_mean    FLOAT,
    bb_start            SMALLINT,
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (participant_id, date)
);

CREATE TABLE songs (
    id              SERIAL PRIMARY KEY,
    spotify_uri     VARCHAR(100) UNIQUE NOT NULL,
    name            VARCHAR(255),
    artists         VARCHAR(255),
    tempo           FLOAT,
    energy          FLOAT,
    valence         FLOAT,
    acousticness    FLOAT,
    danceability    FLOAT,
    loudness        FLOAT,
    duration_ms     INTEGER
);

CREATE TABLE participant_songs (
    participant_id  INTEGER REFERENCES participants(id) ON DELETE CASCADE,
    song_id         INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    playlist_type   VARCHAR(10) CHECK (playlist_type IN ('Calm','Neutral','Energy')),
    PRIMARY KEY (participant_id, song_id, playlist_type)
);

-- For cross-participant recommendations
CREATE TABLE session_songs (
    session_id  INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    song_id     INTEGER REFERENCES songs(id),
    position    SMALLINT,
    PRIMARY KEY (session_id, song_id)
);

-- Index for common lookup patterns
CREATE INDEX idx_sessions_participant ON sessions(participant_id);
CREATE INDEX idx_sessions_date       ON sessions(date);
CREATE INDEX idx_sessions_playlist   ON sessions(playlist_type);
```

---

## Migration Script

A Python migration script (`scripts/migrate_to_postgres.py`) would:

1. Connect via SQLAlchemy: `postgresql+psycopg2://rem_user:password@localhost:5432/moodtune`
2. Insert participants from `PARTICIPANTS` list.
3. For each participant, read `data/wearables/{p}/processed/session_biometrics.csv`
   and insert rows into `sessions`.
4. For each participant, read playlist CSVs from `data/playlists/{p}/playlists_generated/`
   and upsert into `songs` + `participant_songs`.
5. Run idempotently (use `ON CONFLICT DO NOTHING` for all inserts).

Key dependency: `pip install sqlalchemy psycopg2-binary`

---

## Cross-Participant Playlist Query

Once all participant songs are in the database, generate a "community" playlist
using songs that produced the best mood outcomes for *other* participants with
a similar biometric profile:

```sql
-- Songs from the calm playlist of other participants that had high mood improvement
SELECT
    s.name, s.artists, s.tempo, s.energy, s.acousticness,
    AVG(sess.mood_after_score - sess.mood_before_score) AS avg_mood_lift,
    COUNT(DISTINCT ps.participant_id) AS participant_count
FROM songs s
JOIN participant_songs ps ON s.id = ps.song_id
JOIN sessions sess ON sess.participant_id = ps.participant_id
    AND sess.playlist_type = ps.playlist_type
WHERE ps.playlist_type = 'Calm'
  AND ps.participant_id != :current_participant_id
  AND sess.mood_after_score IS NOT NULL
GROUP BY s.id, s.name, s.artists, s.tempo, s.energy, s.acousticness
HAVING COUNT(DISTINCT ps.participant_id) >= 2   -- seen by multiple participants
ORDER BY avg_mood_lift DESC
LIMIT 20;
```

---

## Notes

- **Raspberry Pi model**: Pi 4 (4GB RAM) recommended; Pi 3 can run postgres but
  may be slow with pymc/JAX computations. Keep ML scripts running locally, only
  move data storage + web serving to the Pi.
- **Domain**: Set up a free subdomain or use a home IP with DynDNS for Caddy's
  Let's Encrypt certificate.
- **Backups**: Add a `pg_dump` cron job or use `pg_auto_failover` for WAL
  streaming. At minimum: `docker exec postgres pg_dump -U rem_user moodtune > backup.sql`
- **Security**: Never expose port 5432 directly to the internet. Use SSH tunnel
  or VPN (WireGuard) for direct database access.
- **App changes needed**: Replace `_read_csv()` calls in `utils/data_loader.py`
  with SQLAlchemy queries. Keep CSV fallback for local development.
