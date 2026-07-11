"""
Entry point for the H2 Sports MLB dashboard.

Streamlit 1.4x+ deprecated the automatic `pages/` folder discovery in favor of the explicit
st.navigation API. On recent versions the old auto-discovery can reset navigation to the entry
page on every rerun (the "jumps back to Home on any click" bug). Declaring the pages explicitly
here fixes that — navigation state is stable across reruns.

DEPLOY NOTE: set the app's "Main file path" to  streamlit_app.py  (not Home.py).
set_page_config is called ONCE here and applies to every page; the individual page files no
longer call it.
"""

import streamlit as st
from pathlib import Path

st.set_page_config(page_title="H2 Sports MLB Dashboard", page_icon="⚾", layout="wide")

_HERE = Path(__file__).parent
_PAGES_DIR = _HERE / "views"

# Clean titles + icons keyed by the page-file's leading number, so the sidebar looks right no
# matter how the emoji in the filenames are encoded on disk.
_META = {
    "0": ("Command Center", "🏆"), "1": ("Pitching Lab", "🎯"), "2": ("Dinger Engine", "💣"),
    "3": ("Edge Board", "📈"),      "4": ("Bet Log", "📒"),      "5": ("Best Bets", "⭐"),
    "6": ("Retrospective", "🔍"),   "7": ("Media Room", "📣"),   "8": ("Podcast Studio", "🎙️"),
    "9": ("Track Record", "📊"),
}

# Home landing first (default), then the numbered pages in order.
pages = [st.Page(str(_HERE / "Home.py"), title="Home", icon="⚾", default=True)]
for f in sorted(_PAGES_DIR.glob("*.py")):
    title, icon = _META.get(f.name[0], (f.stem, "📄"))
    pages.append(st.Page(str(f), title=title, icon=icon))

st.navigation(pages).run()
