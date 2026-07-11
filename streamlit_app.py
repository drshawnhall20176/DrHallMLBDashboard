"""
Entry point for the H2 Sports MLB dashboard (explicit st.navigation).
 
Each page is given a STABLE, clean url_path so navigation state round-trips across reruns even
though the page filenames contain emoji. Without an explicit url_path, Streamlit derives the slug
from the (emoji-escaped) filename, which can fail to match on rerun and silently fall back to the
default page (Home) — the "every click goes back to Home" bug.
 
DEPLOY NOTE: set the app's "Main file path" to  streamlit_app.py  (not Home.py).
"""
 
import streamlit as st
from pathlib import Path
 
st.set_page_config(page_title="H2 Sports MLB Dashboard", page_icon="⚾", layout="wide")
 
_HERE = Path(__file__).parent
_VIEWS = _HERE / "views"
 
# leading-digit -> (title, icon, stable url slug). The url_path is the key fix: it pins each
# page to a predictable URL so reruns keep you on the same page instead of defaulting to Home.
_META = {
    "0": ("Command Center", "🏆", "command_center"),
    "1": ("Pitching Lab",   "🎯", "pitching_lab"),
    "2": ("Dinger Engine",  "💣", "dinger_engine"),
    "3": ("Edge Board",     "📈", "edge_board"),
    "4": ("Bet Log",        "📒", "bet_log"),
    "5": ("Best Bets",      "⭐", "best_bets"),
    "6": ("Retrospective",  "🔍", "retrospective"),
    "7": ("Media Room",     "📣", "media_room"),
    "8": ("Podcast Studio", "🎙️", "podcast_studio"),
    "9": ("Track Record",   "📊", "track_record"),
}
 
# Home is the landing page but NOT a forced default fallback (default= is intentionally omitted,
# so a rerun on any other page stays on that page).
pages = [st.Page(str(_HERE / "Home.py"), title="Home", icon="⚾", url_path="home")]
for f in sorted(_VIEWS.glob("*.py")):
    title, icon, slug = _META.get(f.name[0], (f.stem, "📄", f"page_{f.name[0]}"))
    pages.append(st.Page(str(f), title=title, icon=icon, url_path=slug))
 
st.navigation(pages).run()
