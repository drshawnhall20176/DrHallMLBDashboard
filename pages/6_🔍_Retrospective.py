"""
Retrospective — how did the model's board hold up against what actually happened?

A MODEL REVIEW, not an outlier hunt. It grades the pre-game probabilities against real
results and shows where the model ranked the players who actually produced. It never mines
for new variables to explain a specific surprise after the fact.
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

import mlb_engine as E
import projections as P
import statcast_data as SC
import weather as WX
import retro as R

st.set_page_config(page_title="Retrospective", page_icon="🔍", layout="wide")
st.title("🔍 Retrospective")
st.caption("How the model's pre-game board lined up with what actually happened")


@st.cache_data(ttl=3600, show_spinner=False)
def load_statcast():
    return SC.load()


@st.cache_data(ttl=1800, show_spinner=False)
def load_weather(meta_keys: tuple):
    out = {}
    for vid, gdate, vname in meta_keys:
        if vid is not None and vid not in out:
            try:
                out[vid] = WX.get_game_weather(vid, gdate, vname)
            except Exception:
                out[vid] = None
    return out


@st.cache_data(ttl=600, show_spinner=False)
def load_retro(date_str: str, fip_constant: float):
    rows, meta = E.build_slate(date_str, fip_constant)
    sc, k = load_statcast()
    wx = load_weather(tuple((m.get("venue_id"), m.get("game_date"), m.get("venue")) for m in meta))
    for r in rows:
        w = wx.get(r.get("_venue_id"))
        r["_weather_hr"] = w["hr_factor"] if w else 1.0
    P.enrich_hitter_rows(rows, seed=7, statcast=sc, statcast_k=k)
    pitcher_rows = P.build_pitcher_projection_rows(rows, meta, seed=11)
    plays = P.build_best_bets(rows, pitcher_rows)
    results = E.get_player_results(date_str)
    graded, summary = R.grade_slate(plays, results)
    homers = R.homer_report(plays, results)
    return graded, summary, homers, len(meta), len(results)


c1, c2 = st.columns([2, 1])
with c1:
    target = st.date_input("Slate to review", datetime.now() - timedelta(days=1))
with c2:
    fip_constant = st.number_input("FIP constant", value=E.FIP_CONSTANT_DEFAULT, step=0.01)
date_str = target.strftime("%Y-%m-%d")

st.warning("**Approximate, for exploration.** Rebuilding a past slate uses *current*-season "
           "rates, so recent dates have little look-ahead but older dates have more. For "
           "rigorous, point-in-time proof, the **Bet Log** (which saved the model's probability "
           "at bet time) is the real scorecard. Read this as a model review, not a P&L.", icon="⚠️")

with st.spinner("Rebuilding the board and pulling results..."):
    graded, summary, homers, n_games, n_results = load_retro(date_str, fip_constant)

if not summary["graded"]:
    st.info("No completed games with results for this date yet. Pick a date whose games are final.")
    st.stop()

st.caption(f"{n_games} games · {summary['graded']} plays graded · {n_results} players with results")

# --- headline: the homer report -------------------------------------------
st.subheader("🎯 Could we have caught it? — players who homered")
st.caption("Of the hitters who actually went deep, where did the model rank them in HR "
           "probability *before* the game. High rank = the model surfaced them; deep in the "
           "list = the data says it was genuinely random.")
hc1, hc2, hc3 = st.columns(3)
hc1.metric("Caught", len(homers["caught"]),
           help=f"Homered AND ranked in the model's top {homers['cutoff']} of {homers['total_ranked']} HR plays")
hc2.metric("Ranked low", len(homers["missed"]), help="Homered but the model ranked them deep")
hc3.metric("Off the board", homers["unprojected"], help="Subs/call-ups not in a projected lineup")

if homers["caught"]:
    cdf = pd.DataFrame(homers["caught"])
    cdf["Rank"] = cdf.apply(lambda r: f"#{r['Rank']} of {r['OfTotal']}", axis=1)
    st.dataframe(
        cdf[["Player", "HR", "ModelProb", "Rank"]].rename(columns={"ModelProb": "Model HR%"})
        .style.format({"Model HR%": "{:.0%}"}),
        hide_index=True, use_container_width=True)
    st.caption("These are the wins worth showing: non-obvious bats the model ranked highly that "
               "actually delivered — surfaced by matchup, platoon, Statcast, and weather, not name value.")
else:
    st.caption("No homers fell inside the model's top HR plays on this date.")

# --- model accuracy --------------------------------------------------------
st.divider()
st.subheader("📊 How the model's leans did")
m1, m2, m3 = st.columns(3)
m1.metric("Plays graded", summary["graded"])
m2.metric("Hit rate", f"{summary['hit_rate']:.0%}" if summary["hit_rate"] is not None else "—")
m3.metric("Hits", summary["hits"])

if summary["tiers"]:
    st.markdown("**Hit rate by conviction tier** — if the model ranks well, stronger leans hit more often")
    st.dataframe(pd.DataFrame(summary["tiers"]).rename(
        columns={"tier": "Conviction", "n": "Plays", "hit_rate": "Hit rate"})
        .style.format({"Hit rate": "{:.0%}"}), hide_index=True, use_container_width=True)

cal = summary["calibration"]
if cal:
    fig, ax = plt.subplots(figsize=(5, 4.5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="perfect")
    ax.scatter([c["predicted"] for c in cal], [c["actual"] for c in cal],
               s=[max(40, c["n"] * 6) for c in cal], color="#7c3aed", alpha=0.75, zorder=3)
    ax.set_xlabel("Model predicted"); ax.set_ylabel("Actual hit rate")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_title("Calibration (this slate)")
    ax.legend(loc="upper left", fontsize=8); ax.grid(alpha=0.2)
    st.pyplot(fig)
    st.caption("One slate is a tiny sample — points won't sit perfectly on the line. The Bet Log's "
               "calibration, accumulated over many bets, is the trustworthy version.")

# --- full graded board -----------------------------------------------------
st.divider()
st.subheader("Full graded board")
only = st.radio("Show", ["All graded", "Hits only", "Misses only"], horizontal=True)
gdf = pd.DataFrame([g for g in graded if g["Hit"] is not None])
if only == "Hits only":
    gdf = gdf[gdf["Hit"]]
elif only == "Misses only":
    gdf = gdf[~gdf["Hit"]]
gdf = gdf.sort_values("Conviction", ascending=False)
gdf["Result"] = gdf["Hit"].map({True: "✓", False: "✗"})
show = gdf[["Conviction", "Player", "Market", "Side", "Line", "ModelProb", "Actual", "Result", "Why"]]
st.dataframe(
    show.rename(columns={"ModelProb": "Model %", "Why": "Why the model liked it"})
    .style.format({"Model %": "{:.0%}", "Conviction": "{:.2f}×", "Line": "{:g}"}),
    hide_index=True, use_container_width=True, height=480)
