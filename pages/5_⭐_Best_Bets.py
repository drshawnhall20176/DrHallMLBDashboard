"""
Best Bets — the model's strongest leans across the whole slate, with reasoning.

Scans every game and all seven markets, ranks plays by conviction (how far the model
diverges from a typical line of that type), shows WHY for each, and slices by start-time
window so you can target the afternoon / evening / late games in turn.

Honest by design: these are model CANDIDATES, not locks and not guaranteed value. Conviction
is not expected value — check the live price on the Edge Board, and let CLV + calibration in
the Bet Log be the judge.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

import mlb_engine as E
import projections as P
import statcast_data as SC
import weather as WX

st.set_page_config(page_title="Best Bets", page_icon="⭐", layout="wide")
st.title("⭐ Best Bets")
st.caption("The model's strongest leans across the slate — ranked, reasoned, and by time slot")

eastern = pytz.timezone("US/Eastern")


def game_dt(iso_utc):
    if not iso_utc:
        return None
    try:
        return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(eastern)
    except (ValueError, TypeError):
        return None


def slot_of(dt):
    if dt is None:
        return "TBD"
    h = dt.hour
    if h < 17:
        return "Afternoon"
    if h < 20:
        return "Evening"
    return "Late"


SLOT_ORDER = {"Afternoon": 0, "Evening": 1, "Late": 2, "TBD": 3}


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


@st.cache_data(ttl=300, show_spinner=False)
def load_best_bets(date_str: str, fip_constant: float):
    rows, meta = E.build_slate(date_str, fip_constant)
    sc, k = load_statcast()
    wx = load_weather(tuple((m.get("venue_id"), m.get("game_date"), m.get("venue")) for m in meta))
    for r in rows:
        w = wx.get(r.get("_venue_id"))
        r["_weather_hr"] = w["hr_factor"] if w else 1.0
    P.enrich_hitter_rows(rows, seed=7, statcast=sc, statcast_k=k)
    pitcher_rows = P.build_pitcher_projection_rows(rows, meta, seed=11)
    plays = P.build_best_bets(rows, pitcher_rows)
    # attach time + slot by game label
    slot_by_game = {m["label"]: (game_dt(m.get("game_date")), m.get("venue")) for m in meta}
    for pl in plays:
        dt, _ = slot_by_game.get(pl["Game"], (None, None))
        pl["Slot"] = slot_of(dt)
        pl["Time"] = dt.strftime("%I:%M %p").lstrip("0") + " ET" if dt else "TBD"
    return plays, len(meta), (len(sc) if sc else 0)


c1, c2 = st.columns([2, 1])
with c1:
    target = st.date_input("Slate date", datetime.now())
with c2:
    fip_constant = st.number_input("FIP constant", value=E.FIP_CONSTANT_DEFAULT, step=0.01)
date_str = target.strftime("%Y-%m-%d")

with st.spinner("Scanning the slate..."):
    plays, n_games, n_sc = load_best_bets(date_str, fip_constant)

if not plays:
    st.info("No plays for this date. Pick a date with scheduled MLB games.")
    st.stop()

st.caption(f"{n_games} games scanned · {len(plays)} candidate plays · "
           f"Statcast {'on' if n_sc else 'off'}")

st.info("These are the model's strongest **leans**, ranked by **conviction** = model probability "
        "÷ the typical probability for that prop type. Conviction is *not* expected value — a high "
        "lean still needs a fair price. Check the live number on the **Edge Board**, then let CLV and "
        "calibration in the **Bet Log** prove whether the model's right. Not locks.", icon="🧭")

# --- filters ---------------------------------------------------------------
slots_present = sorted({p["Slot"] for p in plays}, key=lambda s: SLOT_ORDER.get(s, 9))
f1, f2, f3 = st.columns([1, 2, 1])
with f1:
    slot_pick = st.selectbox("Time slot", ["All slate"] + slots_present)
with f2:
    markets = sorted({p["Market"] for p in plays})
    mkt_pick = st.multiselect("Markets", markets, default=markets)
with f3:
    min_conv = st.slider("Min conviction", 1.0, 3.0, 1.2, 0.1)

view = [p for p in plays
        if (slot_pick == "All slate" or p["Slot"] == slot_pick)
        and p["Market"] in mkt_pick and p["Conviction"] >= min_conv]

if not view:
    st.warning("No plays match these filters — loosen the conviction or market filter.")
    st.stop()

# --- per-slot summary ------------------------------------------------------
counts = pd.Series([p["Slot"] for p in view]).value_counts()
cols = st.columns(len(slots_present) + 1)
cols[0].metric("Plays shown", len(view))
for i, s in enumerate(slots_present, start=1):
    cols[i].metric(s, int(counts.get(s, 0)))

# --- the board -------------------------------------------------------------
df = pd.DataFrame(view)[["Conviction", "Time", "Slot", "Player", "Team", "Market", "Side",
                         "Line", "ModelProb", "Fair", "Game", "Why"]]
df = df.rename(columns={"ModelProb": "Model %", "Why": "Why the model likes it"})
st.dataframe(
    df.style.format({"Model %": "{:.0%}", "Line": "{:g}", "Conviction": "{:.2f}×",
                     "Fair": "{:+d}"})
    .background_gradient(cmap="Greens", subset=["Conviction"]),
    use_container_width=True, hide_index=True, height=600)

st.caption("Conviction shades darker for stronger leans. 'Fair' is the model's fair price — bet "
           "only if the live price beats it. Log plays from the Edge Board once you've checked the number.")

with st.expander("How 'best' is defined here (read me)"):
    st.markdown(
        """
This board ranks by **conviction**, defined transparently as the model's probability for the
favored side divided by the *typical* probability for that prop type (e.g. ~11% for a 1+ HR,
~50% for a pitcher K over). A 2.0× HR lean means the model likes that hitter to homer about
twice as often as a typical HR prop — i.e. the model strongly diverges from the baseline.

**Why conviction and not "locks":** a high conviction is where edges *tend* to live, but it is
**not** expected value on its own — a great probability at a bad price is a bad bet. The honest
workflow is: this board finds candidates and explains the reasoning, the **Edge Board** checks
them against the live market for actual +EV, and the **Bet Log** proves over time (via CLV and
calibration) whether the model's leans actually beat the market. Treat everything here as a
starting point for analysis, never a guarantee.
"""
    )
