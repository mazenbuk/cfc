import os
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

CHELSEA_TEAM_ID = 49

# ---------- CONNECT DATABASE ----------

@st.cache_resource
def get_engine():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "chelsea_dw")
    user = os.getenv("POSTGRES_USER", "chelsea_admin")
    password = os.getenv("POSTGRES_PASSWORD", "")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


@st.cache_data(ttl=300)
def run_query(query: str) -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(query, engine)


# ---------- QUERY DATA ----------

def load_matches():
    query = """
        SELECT
            m.match_id, d.full_date, d.season, m.competition,
            th.team_name AS home_team, ta.team_name AS away_team,
            m.home_goals, m.away_goals, m.result
        FROM fact_match m
        JOIN dim_date d ON m.date_id = d.date_id
        JOIN dim_team th ON m.home_team_id = th.team_id
        JOIN dim_team ta ON m.away_team_id = ta.team_id
        ORDER BY d.full_date DESC
    """
    return run_query(query)


def load_player_stats():
    query = """
        SELECT
            p.full_name, p.position,
            COUNT(DISTINCT s.match_id) AS matches_played,
            SUM(s.minutes_played) AS minutes,
            SUM(s.goals) AS goals,
            SUM(s.assists) AS assists,
            SUM(s.shots_total) AS shots,
            SUM(s.yellow_cards) AS yellow_cards,
            SUM(s.red_cards) AS red_cards,
            ROUND(AVG(s.rating)::numeric, 2) AS avg_rating
        FROM fact_player_stat s
        JOIN dim_player p ON s.player_id = p.player_id
        GROUP BY p.full_name, p.position
        ORDER BY goals DESC, assists DESC
    """
    return run_query(query)


def load_gk_stats():
    query = """
        SELECT
            p.full_name,
            COUNT(DISTINCT s.match_id) AS matches_played,
            SUM(s.saves) AS total_saves,
            SUM(s.goals_conceded) AS goals_conceded,
            SUM(CASE WHEN s.clean_sheet THEN 1 ELSE 0 END) AS clean_sheets
        FROM fact_gk_stat s
        JOIN dim_player p ON s.player_id = p.player_id
        GROUP BY p.full_name
        ORDER BY clean_sheets DESC, total_saves DESC
    """
    return run_query(query)


# ---------- UI ----------

st.set_page_config(page_title="Chelsea FC Dashboard", page_icon="🔵", layout="wide")

st.title("🔵 Chelsea FC — Data Dashboard")

try:
    matches = load_matches()
    player_stats = load_player_stats()
    gk_stats = load_gk_stats()
except Exception as e:
    st.error(f"Gagal connect ke database: {e}")
    st.stop()

if matches.empty:
    st.warning("Belum ada data pertandingan")
    st.stop()

# Filter musim (sidebar)
seasons = sorted(matches["season"].dropna().unique(), reverse=True)
selected_season = st.sidebar.selectbox("Musim", options=["Semua"] + list(seasons))

if selected_season != "Semua":
    matches_f = matches[matches["season"] == selected_season]
else:
    matches_f = matches

# Hanya pertandingan yang sudah selesai (punya skor & result)
played = matches_f.dropna(subset=["result"])

tab_overview, tab_matches, tab_players, tab_gk = st.tabs(
    ["📊 Overview", "📅 Pertandingan", "⚽ Statistik Pemain", "🧤 Statistik Kiper"]
)

# ---------- TAB 1: OVERVIEW ----------
with tab_overview:
    col1, col2, col3, col4, col5 = st.columns(5)

    wins = (played["result"] == "W").sum()
    draws = (played["result"] == "D").sum()
    losses = (played["result"] == "L").sum()
    total = len(played)
    win_rate = (wins / total * 100) if total > 0 else 0

    goals_for = played.apply(
        lambda r: r["home_goals"] if r["home_team"] == "Chelsea" else r["away_goals"], axis=1
    ).sum()
    goals_against = played.apply(
        lambda r: r["away_goals"] if r["home_team"] == "Chelsea" else r["home_goals"], axis=1
    ).sum()

    col1.metric("Main", total)
    col2.metric("Menang", int(wins))
    col3.metric("Seri", int(draws))
    col4.metric("Kalah", int(losses))
    col5.metric("Win Rate", f"{win_rate:.1f}%")

    col_a, col_b = st.columns(2)
    col_a.metric("Gol Dicetak", int(goals_for))
    col_b.metric("Gol Kebobolan", int(goals_against))

    st.subheader("Distribusi Hasil Pertandingan")
    result_counts = played["result"].map({"W": "Menang", "D": "Seri", "L": "Kalah"}).value_counts()
    fig = px.pie(
        values=result_counts.values,
        names=result_counts.index,
        color=result_counts.index,
        color_discrete_map={"Menang": "#1E824C", "Seri": "#B7950B", "Kalah": "#C0392B"},
        hole=0.4,
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 2: PERTANDINGAN ----------
with tab_matches:
    st.subheader("Riwayat Pertandingan")

    display_df = matches_f.copy()
    display_df["Skor"] = display_df["home_goals"].fillna("-").astype(str) + " - " + display_df["away_goals"].fillna("-").astype(str)
    display_df = display_df[["full_date", "competition", "home_team", "Skor", "away_team", "result"]]
    display_df.columns = ["Tanggal", "Kompetisi", "Kandang", "Skor", "Tandang", "Hasil"]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.subheader("Tren Gol per Pertandingan")
    trend_df = played.sort_values("full_date").copy()
    trend_df["Gol Chelsea"] = trend_df.apply(
        lambda r: r["home_goals"] if r["home_team"] == "Chelsea" else r["away_goals"], axis=1
    )
    trend_df["Gol Lawan"] = trend_df.apply(
        lambda r: r["away_goals"] if r["home_team"] == "Chelsea" else r["home_goals"], axis=1
    )
    fig_trend = px.line(
        trend_df, x="full_date", y=["Gol Chelsea", "Gol Lawan"],
        markers=True, labels={"full_date": "Tanggal", "value": "Gol", "variable": ""}
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ---------- TAB 3: STATISTIK PEMAIN ----------
with tab_players:
    st.subheader("Top Scorer & Assist")

    if player_stats.empty:
        st.info("Belum ada data statistik pemain (fact_player_stat masih kosong).")
    else:
        col1, col2 = st.columns(2)

        top_scorers = player_stats.nlargest(10, "goals")
        fig_goals = px.bar(
            top_scorers, x="goals", y="full_name", orientation="h",
            title="Top 10 Pencetak Gol", labels={"full_name": "", "goals": "Gol"}
        )
        fig_goals.update_layout(yaxis={"categoryorder": "total ascending"})
        col1.plotly_chart(fig_goals, use_container_width=True)

        top_assists = player_stats.nlargest(10, "assists")
        fig_assists = px.bar(
            top_assists, x="assists", y="full_name", orientation="h",
            title="Top 10 Assist", labels={"full_name": "", "assists": "Assist"}
        )
        fig_assists.update_layout(yaxis={"categoryorder": "total ascending"})
        col2.plotly_chart(fig_assists, use_container_width=True)

        st.subheader("Tabel Lengkap Statistik Pemain")
        st.dataframe(
            player_stats.rename(columns={
                "full_name": "Nama", "position": "Posisi", "matches_played": "Main",
                "minutes": "Menit", "goals": "Gol", "assists": "Assist",
                "shots": "Tembakan", "yellow_cards": "Kartu Kuning",
                "red_cards": "Kartu Merah", "avg_rating": "Rating Rata-rata"
            }),
            use_container_width=True, hide_index=True
        )

# ---------- TAB 4: STATISTIK KIPER ----------
with tab_gk:
    st.subheader("Statistik Kiper")

    if gk_stats.empty:
        st.info("Belum ada data statistik kiper (fact_gk_stat masih kosong).")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Clean Sheet", int(gk_stats["clean_sheets"].sum()))
        col2.metric("Total Saves", int(gk_stats["total_saves"].sum()))
        col3.metric("Total Gol Kebobolan", int(gk_stats["goals_conceded"].sum()))

        fig_gk = px.bar(
            gk_stats, x="full_name", y=["total_saves", "clean_sheets"],
            barmode="group", title="Perbandingan Kiper",
            labels={"full_name": "", "value": "Jumlah", "variable": ""}
        )
        st.plotly_chart(fig_gk, use_container_width=True)

        st.dataframe(
            gk_stats.rename(columns={
                "full_name": "Nama", "matches_played": "Main",
                "total_saves": "Saves", "goals_conceded": "Gol Kebobolan",
                "clean_sheets": "Clean Sheet"
            }),
            use_container_width=True, hide_index=True
        )

st.sidebar.divider()
st.sidebar.caption("Chelsea FC Data Pipeline")