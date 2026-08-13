import os
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "chelsea_dw"),
    "user": os.getenv("POSTGRES_USER", "chelsea_admin"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def _read_csv(filename: str) -> pd.DataFrame:
    path = PROCESSED_DIR / filename
    if not path.exists():
        print(f"File tidak ditemukan: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    df = df.astype(object)
    return df.where(pd.notnull(df), None)


def _upsert(conn, table: str, df: pd.DataFrame, conflict_col: str, update_cols: list):
    """Generic UPSERT: insert semua baris df, update kalau conflict_col sudah ada."""
    if df.empty:
        print(f"Tidak ada data untuk tabel {table}")
        return

    cols = list(df.columns)
    values = [tuple(row) for row in df.itertuples(index=False, name=None)]

    set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
    query = f"""
        INSERT INTO {table} ({", ".join(cols)})
        VALUES %s
        ON CONFLICT ({conflict_col}) DO UPDATE SET {set_clause}
    """

    with conn.cursor() as cur:
        execute_values(cur, query, values)
    conn.commit()
    print(f"{table}: {len(df)} baris terupsert")


# ---------- LOAD PER TABEL ----------

def load_dim_team(conn):
    df = _read_csv("dim_team.csv")
    _upsert(conn, "dim_team", df, "team_id",
            ["team_name", "league", "founded_year", "logo_url"])


def load_dim_venue(conn):
    df = _read_csv("dim_venue.csv")
    _upsert(conn, "dim_venue", df, "venue_id",
            ["venue_name", "city", "capacity"])


def load_dim_player(conn):
    df = _read_csv("dim_player.csv")
    _upsert(conn, "dim_player", df, "player_id",
            ["team_id", "full_name", "position", "nationality",
             "birth_date", "height_cm", "weight_kg"])


def load_dim_date(conn) -> dict:
    df = _read_csv("dim_date.csv")
    if df.empty:
        return {}

    cols = list(df.columns)
    values = [tuple(row) for row in df.itertuples(index=False, name=None)]

    query = f"""
        INSERT INTO dim_date ({", ".join(cols)})
        VALUES %s
        ON CONFLICT (full_date) DO NOTHING
    """
    with conn.cursor() as cur:
        execute_values(cur, query, values)
    conn.commit()
    print(f"dim_date: {len(df)} baris diproses")

    with conn.cursor() as cur:
        cur.execute("SELECT date_id, full_date FROM dim_date")
        rows = cur.fetchall()
    return {str(full_date): date_id for date_id, full_date in rows}


def load_fact_match(conn, date_map: dict):
    df = _read_csv("fact_match.csv")
    if df.empty:
        print("Tidak ada data untuk fact_match")
        return

    df["date_id"] = df["full_date"].astype(str).map(date_map)
    df["date_id"] = df["date_id"].where(pd.notnull(df["date_id"]), None)
    df = df.drop(columns=["full_date", "status"], errors="ignore")

    _upsert(conn, "fact_match", df, "match_id",
            ["date_id", "venue_id", "home_team_id", "away_team_id",
             "competition", "home_goals", "away_goals", "result", "possession_pct"])


def load_fact_player_stat(conn):
    df = _read_csv("fact_player_stat.csv")
    _upsert(conn, "fact_player_stat", df, "match_id, player_id",
            ["team_id", "minutes_played", "goals", "assists", "shots_total",
             "shots_on_target", "passes_total", "passes_accuracy", "tackles",
             "yellow_cards", "red_cards", "rating"])


def load_fact_gk_stat(conn):
    df = _read_csv("fact_gk_stat.csv")
    _upsert(conn, "fact_gk_stat", df, "match_id, player_id",
            ["minutes_played", "saves", "goals_conceded", "clean_sheet"])


# ---------- MAIN ----------

def main():
    print("Menghubungkan ke PostgreSQL")
    conn = get_connection()
    print(f"Terhubung ke {DB_CONFIG['dbname']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}\n")

    try:
        print("[1/4] Loading dimension tables (team, venue)")
        load_dim_team(conn)
        load_dim_venue(conn)

        print("\n[2/4] Loading dim_date")
        date_map = load_dim_date(conn)

        print("\n[3/4] Loading dim_player")
        load_dim_player(conn)

        print("\n[4/4] Loading fact tables")
        load_fact_match(conn, date_map)
        load_fact_player_stat(conn)
        load_fact_gk_stat(conn)

        print("\nSelesai.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()