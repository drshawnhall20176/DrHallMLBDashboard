"""
clv_capture.py — match open bets to live odds so closing lines can be captured automatically.

The engine is pure and testable: given your open bets and the current odds offers (from
odds_api.parse_event_offers), it returns the price at the SAME book you bet, for the same
player / market / side / line. The runner (capture_closing_lines.py) calls this on a timer
and writes the latest pre-game price into each open bet as its closing line.

Apples-to-apples is the rule: CLV only means something if the close comes from the same book
you took the bet at, so a bet with no book recorded is skipped (reported, not guessed).
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Bet Log display market -> Odds API market key.
MARKET_TO_ODDS_KEY = {
    "Batter HR": "batter_home_runs",
    "Batter Total Bases": "batter_total_bases",
    "Batter Total Hits": "batter_hits",
    "Batter Strikeouts": "batter_strikeouts",
    "Pitcher Strikeouts": "pitcher_strikeouts",
    "Pitcher Outs": "pitcher_outs",
    "Pitcher Walks": "pitcher_walks",
}


def _norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum())


def _side_key(side: str) -> Optional[str]:
    s = (side or "").strip().lower()
    if s.startswith("o") or s == "yes":
        return "over"
    if s.startswith("u") or s == "no":
        return "under"
    return None


def bet_close_price(bet: Dict, offers: List[Dict]) -> Optional[int]:
    """Latest price for this bet at its own book, or None if no clean match.

    `offers` are odds_api.parse_event_offers() dicts:
      {market, player, point, over:{book:price}, under:{book:price}}
    Only offers from NOT-yet-started games should be passed in (the runner enforces this),
    so any match is by definition a live pre-game price."""
    okey = MARKET_TO_ODDS_KEY.get(bet.get("market"))
    book = (bet.get("book") or "").strip().lower()
    side = _side_key(bet.get("side"))
    if not okey or not book or side is None:
        return None

    bplayer = _norm(bet.get("player"))
    bline = bet.get("line")
    is_hr = okey == "batter_home_runs"   # single-line market; ignore point in matching

    for off in offers:
        if off.get("market") != okey or _norm(off.get("player")) != bplayer:
            continue
        if not is_hr and bline is not None and off.get("point") != bline:
            continue
        prices = off.get(side) or {}
        for bk, price in prices.items():
            if bk.strip().lower() == book:
                return int(price)
    return None


def capture_updates(open_bets: List[Dict], offers: List[Dict]) -> Dict:
    """Return {bet_id: close_price} for every open bet that matched a current offer,
    plus a small report of what couldn't be matched and why."""
    updates, no_book, no_match = {}, [], []
    for b in open_bets:
        if not (b.get("book") or "").strip():
            no_book.append(b.get("id"))
            continue
        price = bet_close_price(b, offers)
        if price is not None:
            updates[b["id"]] = price
        else:
            no_match.append(b.get("id"))
    return {"updates": updates, "no_book": no_book, "no_match": no_match}
