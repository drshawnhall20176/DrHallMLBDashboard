"""
Media Room — curated "selections we found interesting," built for a podcast/Discord segment.

Not picks, not locks, not advice. Each selection leads with the plain-English CASE (the model's
reasoning) and carries an honest reality-check line. Designed to be read on air and copy-pasted
into show notes / Discord — the reasoning is the content.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

import mlb_engine as E
import projections as P
import statcast_data as SC
import weather as WX

st.set_page_config(page_title="H2 Media Room", page_icon="📣", layout="wide")

st.markdown("""
<style>
.sel-card {background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid #7c3aed;
           border-radius:10px;padding:14px 18px;margin-bottom:12px;}
.sel-card h4 {margin:0 0 6px;font-size:17px;color:#0f172a;}
.sel-card .case {color:#334155;font-size:14px;margin:2px 0;}
.sel-card .rc {color:#64748b;font-size:13px;font-style:italic;margin-top:6px;}
.sel-badge {display:inline-block;background:#7c3aed;color:#fff;font-size:12px;
            padding:2px 9px;border-radius:999px;margin-left:6px;vertical-align:middle;}
</style>
""", unsafe_allow_html=True)

st.title("📣 H2 Sports Media — Selections")
st.caption("Curated plays we found interesting, with the reasoning — ready for the show and the Discord")

PHRASING = {
    ("Batter HR", "Over"): "to go deep",
    ("Batter Total Bases", "Over"): "for 2+ total bases",
    ("Batter Total Bases", "Under"): "to stay under 2 total bases",
    ("Batter Total Hits", "Over"): "to record a hit",
    ("Batter Total Hits", "Under"): "to be held hitless",
    ("Batter Strikeouts", "Over"): "to strike out",
    ("Batter Strikeouts", "Under"): "to avoid the strikeout",
    ("Pitcher Strikeouts", "Over"): "to clear his strikeout number",
    ("Pitcher Strikeouts", "Under"): "to fall short of his strikeout number",
    ("Pitcher Outs", "Over"): "to work deep into the game",
    ("Pitcher Outs", "Under"): "to have a short outing",
    ("Pitcher Walks", "Over"): "to issue walks",
    ("Pitcher Walks", "Under"): "to keep the walks down",
}


def headline(p):
    verb = PHRASING.get((p["Market"], p["Side"]), f"{p['Side']} {p['Line']:g}")
    vs = f" vs {p['Opp']}" if p.get("Opp") else ""
    return f"{p['Player']} ({p['Team']}) {verb}{vs}"


def reality_check(p):
    prob = f"{p['ModelProb']*100:.0f}%"
    fair = f"{p['Fair']:+d}" if p.get("Fair") is not None else "—"
    return (f"Reality check: the model has this around {prob} to cash — a lean we found "
            f"interesting, not a lock. Fair price near {fair}; only worth backing if you beat it.")


@st.cache_data(ttl=3600, show_spinner=False)
def load_statcast():
    return SC.load()


@st.cache_data(ttl=1800, show_spinner=False)
def load_weather(keys):
    out = {}
    for vid, gdate, vname in keys:
        if vid is not None and vid not in out:
            try:
                out[vid] = WX.get_game_weather(vid, gdate, vname)
            except Exception:
                out[vid] = None
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_selections(date_str, fip_constant, n, cap):
    rows, meta = E.build_slate(date_str, fip_constant)
    sc, k = load_statcast()
    wx = load_weather(tuple((m.get("venue_id"), m.get("game_date"), m.get("venue")) for m in meta))
    for r in rows:
        w = wx.get(r.get("_venue_id"))
        r["_weather_hr"] = w["hr_factor"] if w else 1.0
    P.enrich_hitter_rows(rows, seed=7, statcast=sc, statcast_k=k)
    pr = P.build_pitcher_projection_rows(rows, meta, seed=11)
    plays = P.build_best_bets(rows, pr)
    return P.curate_selections(plays, n=n, per_market_cap=cap), len(meta)


c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    target = st.date_input("Slate date", datetime.now())
with c2:
    n = st.slider("How many selections", 5, 8, 6)
with c3:
    cap = st.slider("Max per market", 1, 3, 2, help="Keeps the segment varied across markets.")
date_str = target.strftime("%Y-%m-%d")

with st.spinner("Curating today's selections..."):
    sel, n_games = load_selections(date_str, E.FIP_CONSTANT_DEFAULT, n, cap)

if not sel:
    st.info("No selections for this date. Pick a date with scheduled games.")
    st.stop()

st.caption(f"{n_games} games scanned · {len(sel)} selections curated across markets")

# --- on-screen cards -------------------------------------------------------
for i, p in enumerate(sel, 1):
    st.markdown(
        f"""<div class="sel-card">
        <h4>{i}. {headline(p)} <span class="sel-badge">{p['Market']}</span></h4>
        <div class="case"><b>The case:</b> {p['Why']}.</div>
        <div class="rc">{reality_check(p)}</div>
        </div>""", unsafe_allow_html=True)

# --- copy-all block (Discord / show notes) ---------------------------------
st.subheader("📋 Copy for the show / Discord")
st.caption("One click the copy icon (top-right of the block) to grab the whole segment.")

lines = [f"🎙️ H2 Sports Media — Selections we found interesting · {date_str}", ""]
for i, p in enumerate(sel, 1):
    lines.append(f"{i}) {headline(p)}")
    lines.append(f"   The case: {p['Why']}.")
    lines.append(f"   {reality_check(p)}")
    lines.append("")
lines.append("⚖️ For entertainment. These are selections we found interesting with our reasoning — "
             "not locks and not betting advice. Variance is real; always check the price and bet "
             "responsibly.")
st.code("\n".join(lines), language=None)

st.caption("Tone is intentionally 'interesting, not locks.' Keeping that language consistent on the "
           "show, the Discord, and here protects the brand and sets honest expectations.")
