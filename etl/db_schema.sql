-- ---------- DIMENSION TABLES ----------

CREATE TABLE IF NOT EXISTS dim_team (
    team_id       INTEGER PRIMARY KEY,
    team_name     VARCHAR(100) NOT NULL,
    league        VARCHAR(100),
    founded_year  INTEGER,
    logo_url      TEXT
);

CREATE TABLE IF NOT EXISTS dim_venue (
    venue_id     INTEGER PRIMARY KEY,
    venue_name   VARCHAR(150),
    city         VARCHAR(100),
    capacity     INTEGER
);

CREATE TABLE IF NOT EXISTS dim_player (
    player_id     INTEGER PRIMARY KEY,
    team_id       INTEGER REFERENCES dim_team(team_id),
    full_name     VARCHAR(150) NOT NULL,
    position      VARCHAR(50),
    nationality   VARCHAR(100),
    birth_date    DATE,
    height_cm     INTEGER,
    weight_kg     INTEGER
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id      SERIAL PRIMARY KEY,
    full_date    DATE UNIQUE NOT NULL,
    season       VARCHAR(20),
    matchweek    INTEGER,
    day_of_week  VARCHAR(15),
    month        INTEGER,
    year         INTEGER
);

-- ---------- FACT TABLES ----------

CREATE TABLE IF NOT EXISTS fact_match (
    match_id       INTEGER PRIMARY KEY,
    date_id        INTEGER REFERENCES dim_date(date_id),
    venue_id       INTEGER REFERENCES dim_venue(venue_id),
    home_team_id   INTEGER REFERENCES dim_team(team_id),
    away_team_id   INTEGER REFERENCES dim_team(team_id),
    competition    VARCHAR(100),
    home_goals     INTEGER,
    away_goals     INTEGER,
    result         VARCHAR(1),
    possession_pct NUMERIC(5,2),
    created_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_player_stat (
    stat_id           SERIAL PRIMARY KEY,
    match_id          INTEGER REFERENCES fact_match(match_id),
    player_id         INTEGER REFERENCES dim_player(player_id),
    team_id           INTEGER REFERENCES dim_team(team_id),
    minutes_played    INTEGER,
    goals             INTEGER DEFAULT 0,
    assists           INTEGER DEFAULT 0,
    shots_total       INTEGER DEFAULT 0,
    shots_on_target   INTEGER DEFAULT 0,
    passes_total      INTEGER DEFAULT 0,
    passes_accuracy   NUMERIC(5,2),
    tackles           INTEGER DEFAULT 0,
    yellow_cards      INTEGER DEFAULT 0,
    red_cards         INTEGER DEFAULT 0,
    rating            NUMERIC(3,1),
    UNIQUE (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS fact_gk_stat (
    stat_id          SERIAL PRIMARY KEY,
    match_id         INTEGER REFERENCES fact_match(match_id),
    player_id        INTEGER REFERENCES dim_player(player_id),
    minutes_played   INTEGER,
    saves            INTEGER DEFAULT 0,
    goals_conceded   INTEGER DEFAULT 0,
    clean_sheet      BOOLEAN DEFAULT FALSE,
    UNIQUE (match_id, player_id)
);

-- ---------- INDEXES ----------

CREATE INDEX IF NOT EXISTS idx_fact_match_date        ON fact_match(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_match_teams        ON fact_match(home_team_id, away_team_id);
CREATE INDEX IF NOT EXISTS idx_fact_player_stat_match  ON fact_player_stat(match_id);
CREATE INDEX IF NOT EXISTS idx_fact_player_stat_player ON fact_player_stat(player_id);
CREATE INDEX IF NOT EXISTS idx_dim_player_team         ON dim_player(team_id);