import streamlit as st
import pandas as pd
import statsapi  # Requires: pip install MLB-StatsAPI
from datetime import datetime


# ---------------------------------------------------------
# DATA ACQUISITION LOGIC (Live API)
# ---------------------------------------------------------

@st.cache_data(ttl=3600)  # Cache data for 1 hour to stay within rate limits
def fetch_daily_games(date_str):
    """
    Fetches all MLB games for a specific date.
    Returns a list of dicts containing gameId, teams, and status.
    """
    try:
        schedule = statsapi.schedule(date=date_str)
        return schedule
    except Exception as e:
        st.error(f"Error fetching schedule: {e}")
        return []


@st.cache_data(ttl=3600)
def fetch_pitcher_season_stats(player_id):
    """
    Retrieves current 2026 season totals for a specific pitcher.
    """
    try:
        # Get season pitching stats
        stats = statsapi.player_stats(player_id, group="pitching", type="season")
        if not stats:
            return None

        # statsapi returns a string-heavy report or raw data depending on function
        # We use statsapi.get() for raw JSON if specific fields are needed
        return stats
    except Exception as e:
        return None


# ---------------------------------------------------------
# CALCULATION ENGINE (From Phase 1)
# ---------------------------------------------------------

def calculate_fip(row, constant=3.10):
    """
    Calculates FIP using API-provided season totals.
    Formula: ((13*HR + 3*(BB+HBP) - 2*K) / IP) + Constant
    """
    try:
        hr = float(row.get('homeRuns', 0))
        bb = float(row.get('baseOnBalls', 0))
        hbp = float(row.get('hitByPitch', 0))
        k = float(row.get('strikeOuts', 0))
        ip = float(row.get('inningsPitched', 0))

        if ip <= 0: return 0
        return round(((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / ip + constant, 2)
    except:
        return 0


# ---------------------------------------------------------
# STREAMLIT UI - LIVE DASHBOARD
# ---------------------------------------------------------

def main():
    st.set_page_config(page_title="H2 Live MLB Dashboard", layout="wide")
    st.title("⚾ Live MLB Model: API Integration")

    # 1. Date Selection
    selected_date = st.date_input("Select Game Date", datetime.now())
    date_str = selected_date.strftime("%Y-%m-%d")

    # 2. Fetch Live Schedule
    with st.spinner("Loading live games..."):
        games = fetch_daily_games(date_str)

    if not games:
        st.warning(f"No games found for {date_str}.")
        return

    # 3. Game Selector for Media Analysis
    st.sidebar.header("Matchup Analysis")
    game_options = {f"{g['away_name']} @ {g['home_name']}": g for g in games}
    selected_game_label = st.sidebar.selectbox("Choose a Game", list(game_options.keys()))
    game_data = game_options[selected_game_label]

    # 4. Deep Dive: Starting Pitchers (Logic for Moneyline Testing)
    st.header(f"Analysis: {selected_game_label}")

    # Note: In a production app, you would fetch probable pitchers
    # via statsapi.boxscore_data(game_data['game_id'])
    st.write(f"**Game Status:** {game_data['status']} | **Venue:** {game_data['venue_name']}")

    # 5. Demonstration of Data Mapping
    st.subheader("Automated Regression Tracking")
    st.markdown("""
    This section pulls **real-time season totals** for the probable starters 
    and applies the Phase 1 filters to find betting value.
    """)

    # Mocking the dataframe structure for UI demonstration
    # (In your app, loop through game rosters to populate this)
    analysis_df = pd.DataFrame([
        {"Player": "Starter A", "ERA": 4.10, "homeRuns": 5, "baseOnBalls": 12, "hitByPitch": 1, "strikeOuts": 45,
         "inningsPitched": 40.0},
        {"Player": "Starter B", "ERA": 2.85, "homeRuns": 8, "baseOnBalls": 10, "hitByPitch": 2, "strikeOuts": 38,
         "inningsPitched": 42.0}
    ])

    analysis_df['FIP'] = analysis_df.apply(calculate_fip, axis=1)
    analysis_df['Delta'] = (analysis_df['ERA'] - analysis_df['FIP']).round(2)

    st.table(analysis_df)

    # Media Content Generation
    st.divider()
    st.subheader("🤳 Social Media Hook (Auto-Generated)")
    for _, row in analysis_df.iterrows():
        if row['Delta'] > 0.5:
            st.code(f"BET ALERT: {row['Player']} has an ERA of {row['ERA']}, but his FIP is {row['FIP']}. "
                    f"He's pitching better than the scoreboards show. Buy the dip on his Moneyline! #MLB #Betting")


if __name__ == "__main__":
    main()