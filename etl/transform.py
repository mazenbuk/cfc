import json
from pathlib import Path
from datetime import datetime

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

CHELSEA_TEAM_ID = 49


# ---------- HELPER ----------

def _load(filename: str):
    path = RAW_DIR / filename
    if not path.exists():
        print(f"File tidak ditemukan: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_csv(df: pd.DataFrame, filename: str):
    path = PROCESSED_DIR / filename
    df.to_csv(path, index=False)
    print(f"Disimpan: {path}  ({len(df)} baris)")


# ---------- TRANSFORM: DIMENSIONS ----------

def transform_dim_team(team_info_raw, fixtures_raw):
    """Ambil Chelsea n semua lawan yang muncul di fixtures."""
    teams = {}

    if team_info_raw:
        t = team_info_raw[0]["team"]
        teams[t["id"]] = {
            "team_id": t["id"],
            "team_name": t["name"],
            "league": "Premier League",
            "founded_year": t.get("founded"),
            "logo_url": t.get("logo"),
        }

    if fixtures_raw:
        for f in fixtures_raw:
            for side in ("home", "away"):
                team = f["teams"][side]
                if team["id"] not in teams:
                    teams[team["id"]] = {
                        "team_id": team["id"],
                        "team_name": team["name"],
                        "league": "Premier League",
                        "founded_year": None,
                        "logo_url": team.get("logo"),
                    }

    df = pd.DataFrame(teams.values())
    _save_csv(df, "dim_team.csv")
    return df


def transform_dim_venue(team_info_raw, fixtures_raw):
    venues = {}

    if team_info_raw:
        v = team_info_raw[0].get("venue")
        if v and v.get("id"):
            venues[v["id"]] = {
                "venue_id": v["id"],
                "venue_name": v.get("name"),
                "city": v.get("city"),
                "capacity": v.get("capacity"),
            }

    if fixtures_raw:
        for f in fixtures_raw:
            v = f["fixture"].get("venue")
            if v and v.get("id") and v["id"] not in venues:
                venues[v["id"]] = {
                    "venue_id": v["id"],
                    "venue_name": v.get("name"),
                    "city": v.get("city"),
                    "capacity": None,
                }

    df = pd.DataFrame(venues.values())
    _save_csv(df, "dim_venue.csv")
    return df


def transform_dim_player(squad_raw, fixture_stats_raw=None):
    rows = []

    if squad_raw:
        for team_block in squad_raw:
            team_id = team_block["team"]["id"]
            for p in team_block.get("players", []):
                rows.append({
                    "player_id": p["id"],
                    "team_id": team_id,
                    "full_name": p.get("name"),
                    "position": p.get("position"),
                    "nationality": None,
                    "birth_date": None,
                    "height_cm": None,
                    "weight_kg": None,
                })

    df = pd.DataFrame(rows).drop_duplicates(subset="player_id")
    known_ids = set(df["player_id"]) if not df.empty else set()

    extra_rows = []
    if fixture_stats_raw:
        seen_extra = set()
        for entry in fixture_stats_raw:
            for team_block in entry["stats"]:
                if team_block["team"]["id"] != CHELSEA_TEAM_ID:
                    continue
                
                for p in team_block.get("players", []):
                    pid = p["player"]["id"]
                    if pid in known_ids or pid in seen_extra:
                        continue
                    
                    seen_extra.add(pid)
                    stats_list = p.get("statistics", [])
                    position = None
                    if stats_list:
                        position = (stats_list[0].get("games") or {}).get("position")
                    extra_rows.append({
                        "player_id": pid,
                        "team_id": CHELSEA_TEAM_ID,
                        "full_name": p["player"].get("name"),
                        "position": position,
                        "nationality": None,
                        "birth_date": None,
                        "height_cm": None,
                        "weight_kg": None,
                    })

    if extra_rows:
        df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)
        df = df.drop_duplicates(subset="player_id")

    _save_csv(df, "dim_player.csv")
    return df


def transform_dim_date(fixtures_raw):
    if not fixtures_raw:
        return pd.DataFrame()

    rows = []
    seen_dates = set()
    for f in fixtures_raw:
        date_str = f["fixture"]["date"][:10]
        if date_str in seen_dates:
            continue
        seen_dates.add(date_str)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        rows.append({
            "full_date": date_str,
            "season": f["league"].get("season"),
            "matchweek": _parse_round(f["league"].get("round")),
            "day_of_week": dt.strftime("%A"),
            "month": dt.month,
            "year": dt.year,
        })

    df = pd.DataFrame(rows)
    _save_csv(df, "dim_date.csv")
    return df


def _parse_round(round_str):
    """'Regular Season - 5' -> 5"""
    if not round_str:
        return None
    try:
        return int(round_str.split("-")[-1].strip())
    except (ValueError, AttributeError):
        return None


# ---------- TRANSFORM: FACTS ----------

def transform_fact_match(fixtures_raw):
    if not fixtures_raw:
        return pd.DataFrame()

    rows = []
    for f in fixtures_raw:
        home_id = f["teams"]["home"]["id"]
        away_id = f["teams"]["away"]["id"]
        home_goals = f["goals"]["home"]
        away_goals = f["goals"]["away"]

        result = None
        if home_goals is not None and away_goals is not None:
            chelsea_is_home = home_id == CHELSEA_TEAM_ID
            chelsea_goals = home_goals if chelsea_is_home else away_goals
            opp_goals = away_goals if chelsea_is_home else home_goals
            if chelsea_goals > opp_goals:
                result = "W"
            elif chelsea_goals < opp_goals:
                result = "L"
            else:
                result = "D"

        rows.append({
            "match_id": f["fixture"]["id"],
            "full_date": f["fixture"]["date"][:10],
            "venue_id": (f["fixture"].get("venue") or {}).get("id"),
            "home_team_id": home_id,
            "away_team_id": away_id,
            "competition": f["league"].get("name"),
            "home_goals": home_goals,
            "away_goals": away_goals,
            "result": result,
            "possession_pct": None,
            "status": f["fixture"]["status"]["short"],
        })

    df = pd.DataFrame(rows)
    _save_csv(df, "fact_match.csv")
    return df


def transform_fact_player_stats(fixture_stats_raw):
    if not fixture_stats_raw:
        return pd.DataFrame(), pd.DataFrame()

    player_rows = []
    gk_rows = []

    for entry in fixture_stats_raw:
        match_id = entry["fixture_id"]
        for team_block in entry["stats"]:
            team_id = team_block["team"]["id"]
            for p in team_block.get("players", []):
                player_id = p["player"]["id"]
                stats_list = p.get("statistics", [])
                if not stats_list:
                    continue
                s = stats_list[0]

                games = s.get("games", {}) or {}
                goals = s.get("goals", {}) or {}
                shots = s.get("shots", {}) or {}
                passes = s.get("passes", {}) or {}
                tackles = s.get("tackles", {}) or {}
                cards = s.get("cards", {}) or {}

                position = (games.get("position") or "").upper()
                minutes = games.get("minutes")

                if team_id != CHELSEA_TEAM_ID:
                    continue

                if position == "G":
                    gk_rows.append({
                        "match_id": match_id,
                        "player_id": player_id,
                        "minutes_played": minutes,
                        "saves": goals.get("saves"),
                        "goals_conceded": goals.get("conceded"),
                        "clean_sheet": (goals.get("conceded") or 0) == 0 and (minutes or 0) > 0,
                    })
                else:
                    player_rows.append({
                        "match_id": match_id,
                        "player_id": player_id,
                        "team_id": team_id,
                        "minutes_played": minutes,
                        "goals": goals.get("total") or 0,
                        "assists": goals.get("assists") or 0,
                        "shots_total": shots.get("total") or 0,
                        "shots_on_target": shots.get("on") or 0,
                        "passes_total": passes.get("total") or 0,
                        "passes_accuracy": passes.get("accuracy"),
                        "tackles": tackles.get("total") or 0,
                        "yellow_cards": cards.get("yellow") or 0,
                        "red_cards": cards.get("red") or 0,
                        "rating": games.get("rating"),
                    })

    df_players = pd.DataFrame(player_rows)
    df_gk = pd.DataFrame(gk_rows)
    _save_csv(df_players, "fact_player_stat.csv")
    _save_csv(df_gk, "fact_gk_stat.csv")
    return df_players, df_gk


# ---------- MAIN ----------

def main():

    team_info_raw = _load("team_info.json")
    squad_raw = _load("squad.json")
    fixtures_raw = _load("fixtures.json")
    fixture_stats_raw = _load("fixture_player_stats.json")

    print("\n[Dimensions]")
    transform_dim_team(team_info_raw, fixtures_raw)
    transform_dim_venue(team_info_raw, fixtures_raw)
    transform_dim_player(squad_raw, fixture_stats_raw)
    transform_dim_date(fixtures_raw)

    print("\n[Facts]")
    transform_fact_match(fixtures_raw)
    transform_fact_player_stats(fixture_stats_raw)

    print("\nSelesai")


if __name__ == "__main__":
    main()