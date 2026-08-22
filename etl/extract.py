import os
import json
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

CHELSEA_TEAM_ID = 49
PREMIER_LEAGUE_ID = 39
SEASON = 2024
MAX_FIXTURES_FOR_STATS = 10

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_DELAY_SECONDS = 3


# ---------- HELPER ----------

def _get(endpoint: str, params: dict, max_retries: int = 3) -> dict:

    if not API_KEY:
        raise EnvironmentError(
            "API_FOOTBALL_KEY tidak ditemukan."
        )

    url = f"{BASE_URL}/{endpoint}"

    for attempt in range(1, max_retries + 1):
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 20 * attempt))
            time.sleep(wait)
            continue

        resp.raise_for_status()
        data = resp.json()

        if data.get("errors"):
            print(f"API error: {data['errors']}")

        remaining = resp.headers.get("x-ratelimit-requests-remaining")
        if remaining is not None:
            print(f"sisa kuota: {remaining})")

        time.sleep(REQUEST_DELAY_SECONDS)
        return data.get("response", [])

    raise RuntimeError(
        f"Gagal fetch {endpoint} setelah {max_retries}x percobaan."
    )


def _save_json(filename: str, data) -> None:
    path = RAW_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Disimpan: {path}  ({len(data) if isinstance(data, list) else 1} item)")


# ---------- EXTRACT FUNCTIONS ----------

def extract_team_info():
    """Info tim Chelsea"""
    print("[1/4] Fetching team info")
    data = _get("teams", {"id": CHELSEA_TEAM_ID})
    _save_json("team_info.json", data)
    return data


def extract_squad():
    """Daftar pemain Chelsea"""
    print("[2/4] Fetching squad")
    data = _get("players/squads", {"team": CHELSEA_TEAM_ID})
    _save_json("squad.json", data)
    return data


def extract_fixtures():
    """Semua fixture Chelsea"""
    print("[3/4] Fetching fixtures")
    data = _get(
        "fixtures",
        {"team": CHELSEA_TEAM_ID, "league": PREMIER_LEAGUE_ID, "season": SEASON},
    )
    _save_json("fixtures.json", data)
    return data


def extract_fixture_stats(fixtures: list):
    """
    Statistik pemain per pertandingan (goals, assists, rating, dll).
    """
    print(f"[4/4] Fetching player stats (max {MAX_FIXTURES_FOR_STATS} fixtures)")

    finished = [f for f in fixtures if f["fixture"]["status"]["short"] == "FT"]
    finished.sort(key=lambda f: f["fixture"]["date"], reverse=True)
    selected = finished[:MAX_FIXTURES_FOR_STATS]

    all_stats = []
    for i, f in enumerate(selected, start=1):
        fixture_id = f["fixture"]["id"]
        print(f"  -> ({i}/{len(selected)}) fixture_id={fixture_id}")
        stats = _get("fixtures/players", {"fixture": fixture_id})
        all_stats.append({"fixture_id": fixture_id, "stats": stats})

    _save_json("fixture_player_stats.json", all_stats)
    return all_stats


# ---------- MAIN ----------

def main():
    extract_team_info()
    extract_squad()
    fixtures = extract_fixtures()

    if fixtures:
        extract_fixture_stats(fixtures)
    else:
        print("Tidak ada fixture")

    print("\nSelesai")


if __name__ == "__main__":
    main()