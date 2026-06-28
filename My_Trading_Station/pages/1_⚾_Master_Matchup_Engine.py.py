import streamlit as st
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------
# DEPENDENCY CHECK (Prevents the red traceback error)
# ---------------------------------------------------------
try:
    import statsapi

    HAS_STATSAPI = True
except ImportError:
    HAS_STATSAPI = False


# ---------------------------------------------------------
# 1. CORE ANALYTICS ENGINE
# ---------------------------------------------------------

def calculate_fip(hr, bb, hbp, k, ip, constant=3.10):
    """Calculates FIP with robust error handling for API data."""
    try:
        # Force conversion to float to handle API strings/None
        stats = [float(x) if x is not None else 0.0 for x in [hr, bb, hbp, k, ip]]
        hr_f, bb_f, hbp_f, k_f, ip_f = stats

        if ip_f <= 0: return 0.0
        return round(((13 * hr_f) + (3 * (bb_f + hbp_f)) - (2 * k_f)) / ip_f + constant, 2)
    except Exception:
        return 0.0


# ---------------------------------------------------------
# 2. LIVE DATA FETCHING
# ---------------------------------------------------------

@st.cache_data(ttl=600)
def get_live_matchups(date_str):
    """Fetches daily games and probable pitchers via MLB-StatsAPI."""
    if not HAS_STATSAPI:
        return []
    try:
        return statsapi.schedule(date=date_str)
    except:
        return []


# ---------------------------------------------------------
# 3. PAGE UI
# ---------------------------------------------------------

def main():
    st.header("🎯 Master Matchup Engine")
    st.caption("Live EV Trading, Regression Profiles, and Game Physics")

    # Friendly error handling for the user
    if not HAS_STATSAPI:
        st.error("⚠️ **Missing Library:** `MLB-StatsAPI` is not installed.")
        st.info("To fix this, open your Pycharm Terminal and run: `pip install MLB-StatsAPI` then restart.")
        return

    # Date Control
    target_date = st.date_input("Analysis Date", datetime.now())
    date_str = target_date.strftime("%Y-%m-%d")

    # Fetch Games
    games = get_live_matchups(date_str)

    if not games:
        st.info("No games found for this date. Select a date with active MLB games.")
        return

    # Matchup Grid
    for game in games:
        with st.expander(f"{game['away_name']} @ {game['home_name']} ({game['status']})"):
            col1, col2 = st.columns(2)

            with col1:
                st.subheader(f"🏟️ {game['away_name']}")
                # Using a placeholder value for demonstration
                mock_stats = {"hr": 10, "bb": 20, "hbp": 2, "k": 90, "ip": 85.0, "era": 3.80}
                fip = calculate_fip(mock_stats['hr'], mock_stats['bb'], mock_stats['hbp'], mock_stats['k'],
                                    mock_stats['ip'])
                st.metric("Model FIP", fip, delta=round(mock_stats['era'] - fip, 2), delta_color="inverse")

            with col2:
                st.subheader(f"🏠 {game['home_name']}")
                mock_stats_h = {"hr": 14, "bb": 15, "hbp": 1, "k": 110, "ip": 90.0, "era": 3.10}
                fip_h = calculate_fip(mock_stats_h['hr'], mock_stats_h['bb'], mock_stats_h['hbp'], mock_stats_h['k'],
                                      mock_stats_h['ip'])
                st.metric("Model FIP", fip_h, delta=round(mock_stats_h['era'] - fip_h, 2), delta_color="inverse")

    # 4. Media Hook Section
    st.divider()
    st.subheader("🤳 Content Creation Helper")
    st.write(
        "Identified discrepancies are flagged above. Use 'Model FIP' lower than 'ERA' as a 'Buy' signal for your audience.")


if __name__ == "__main__":
    main()