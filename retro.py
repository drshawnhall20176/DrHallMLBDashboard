"""
retro.py — grade the model's pre-game board against what actually happened.

This is a MODEL REVIEW, not an outlier-explainer. It scores the probabilities the model
assigned BEFORE the games against real results — it never hunts for new variables to
explain a specific surprise after the fact (that's overfitting, the thing that quietly
destroys a model). The headline view answers the honest version of "could we have caught
that surprise homer?": of the players who actually homered, where did the model rank them?

IMPORTANT CAVEAT (surfaced in the UI): rebuilding a past slate today uses CURRENT-season
rates, not point-in-time rates as of that date, so recent dates have little look-ahead but
older dates have more. For rigorous, point-in-time proof, the Bet Log (which captured the
model's probability at bet time) is the source of truth. This page is for exploration.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

MARKET_STAT = {
    "Batter HR": "hr", "Batter Total Bases": "tb", "Batter Total Hits": "hits",
    "Batter Strikeouts": "so", "Pitcher Strikeouts": "p_k", "Pitcher Outs": "p_outs",
    "Pitcher Walks": "p_bb",
}


def grade_play(market: str, side: str, line: float, actuals: Optional[Dict]) -> Optional[bool]:
    """Did the play hit? None if the player has no stat for that market (didn't appear)."""
    key = MARKET_STAT.get(market)
    if not actuals or key not in actuals:
        return None
    val = actuals[key]
    over_hit = val > line
    return over_hit if side == "Over" else (val < line)   # .5 lines -> no push


def _calibration(graded: List[Dict], n_bins: int = 5) -> List[Dict]:
    settled = [g for g in graded if g["Hit"] is not None]
    if not settled:
        return []
    width, out = 1.0 / n_bins, []
    for i in range(n_bins):
        lo, hi = i * width, (i + 1) * width
        grp = [g for g in settled if (lo <= g["ModelProb"] < hi) or (i == n_bins - 1 and g["ModelProb"] == 1.0)]
        if not grp:
            continue
        out.append({"lo": round(lo, 2), "hi": round(hi, 2),
                    "predicted": round(sum(g["ModelProb"] for g in grp) / len(grp), 3),
                    "actual": round(sum(1 for g in grp if g["Hit"]) / len(grp), 3),
                    "n": len(grp)})
    return out


def grade_slate(plays: List[Dict], results: Dict[int, Dict]) -> Tuple[List[Dict], Dict]:
    """Attach Hit/Actual to every play and summarize. Returns (graded_plays, summary)."""
    graded = []
    for p in plays:
        actuals = results.get(p.get("PlayerId")) if p.get("PlayerId") is not None else None
        hit = grade_play(p["Market"], p["Side"], p["Line"], actuals)
        graded.append({**p, "Hit": hit,
                       "Actual": (actuals or {}).get(MARKET_STAT.get(p["Market"]))})

    matched = [g for g in graded if g["Hit"] is not None]
    # discrimination: hit rate by conviction tier (should trend up if the model ranks well)
    tiers = []
    for lo, hi, label in [(1.75, 99, "≥1.75×"), (1.4, 1.75, "1.4–1.75×"),
                          (1.2, 1.4, "1.2–1.4×"), (0, 1.2, "<1.2×")]:
        grp = [g for g in matched if lo <= g["Conviction"] < hi]
        if grp:
            tiers.append({"tier": label, "n": len(grp),
                          "hit_rate": round(sum(1 for g in grp if g["Hit"]) / len(grp), 3)})

    summary = {
        "total": len(plays), "graded": len(matched),
        "hits": sum(1 for g in matched if g["Hit"]),
        "hit_rate": round(sum(1 for g in matched if g["Hit"]) / len(matched), 3) if matched else None,
        "tiers": tiers,
        "calibration": _calibration(matched),
    }
    return graded, summary


def homer_report(plays: List[Dict], results: Dict[int, Dict], top_n: int = 15) -> Dict:
    """Of the players who actually homered, where did the model rank them in HR probability?

    The honest 'could we have caught it' view: a homer-hitter in the model's top plays was
    catchable pre-game; one ranked deep in the list was, by the data, genuinely random."""
    hr_plays = sorted([p for p in plays if p["Market"] == "Batter HR"],
                      key=lambda x: -x["ModelProb"])
    total = len(hr_plays)
    cutoff = max(top_n, int(total * 0.10))
    rank_by_pid = {p.get("PlayerId"): (i + 1, p["ModelProb"], p["Player"])
                   for i, p in enumerate(hr_plays)}

    caught, missed, unprojected = [], [], 0
    for pid, actuals in results.items():
        if (actuals.get("hr", 0) or 0) < 1:
            continue
        if pid in rank_by_pid:
            rank, prob, name = rank_by_pid[pid]
            entry = {"Player": name, "HR": actuals["hr"], "ModelProb": prob,
                     "Rank": rank, "OfTotal": total}
            (caught if rank <= cutoff else missed).append(entry)
        else:
            unprojected += 1   # not in a lineup we projected (sub, call-up, etc.)

    caught.sort(key=lambda x: x["Rank"])
    missed.sort(key=lambda x: x["Rank"])
    return {"caught": caught, "missed": missed, "unprojected": unprojected,
            "cutoff": cutoff, "total_ranked": total}


def pitcher_k_report(plays: List[Dict], results: Dict[int, Dict], top_n: int = 15) -> Dict:
    """Of pitchers who hit strikeout thresholds, where did the model rank them?"""
    k_plays = sorted([p for p in plays if p["Market"] == "Pitcher Strikeouts"],
                     key=lambda x: -x["ModelProb"])
    total = len(k_plays)
    cutoff = max(top_n, int(total * 0.10))
    rank_by_pid = {p.get("PlayerId"): (i + 1, p["ModelProb"], p["Player"], p["Line"])
                   for i, p in enumerate(k_plays)}

    caught, missed, unprojected = [], [], 0
    for pid, actuals in results.items():
        k_val = actuals.get("p_k", 0) or 0
        if k_val < 1:
            continue
        if pid in rank_by_pid:
            rank, prob, name, line = rank_by_pid[pid]
            # "caught" = actually struck out at or above the line (over bet hit)
            hit_line = k_val >= line
            entry = {"Player": name, "K": k_val, "Line": line, "ModelProb": prob,
                     "Rank": rank, "OfTotal": total, "HitLine": hit_line}
            (caught if rank <= cutoff else missed).append(entry)
        else:
            unprojected += 1

    caught.sort(key=lambda x: x["Rank"])
    missed.sort(key=lambda x: x["Rank"])
    return {"caught": caught, "missed": missed, "unprojected": unprojected,
            "cutoff": cutoff, "total_ranked": total}


def batter_tb_report(plays: List[Dict], results: Dict[int, Dict], top_n: int = 15) -> Dict:
    """Of batters who hit total-bases thresholds, where did the model rank them?"""
    tb_plays = sorted([p for p in plays if p["Market"] == "Batter Total Bases"],
                      key=lambda x: -x["ModelProb"])
    total = len(tb_plays)
    cutoff = max(top_n, int(total * 0.10))
    rank_by_pid = {p.get("PlayerId"): (i + 1, p["ModelProb"], p["Player"], p["Line"])
                   for i, p in enumerate(tb_plays)}

    caught, missed, unprojected = [], [], 0
    for pid, actuals in results.items():
        tb_val = actuals.get("tb", 0) or 0
        if tb_val < 1:
            continue
        if pid in rank_by_pid:
            rank, prob, name, line = rank_by_pid[pid]
            hit_line = tb_val >= line
            entry = {"Player": name, "TB": tb_val, "Line": line, "ModelProb": prob,
                     "Rank": rank, "OfTotal": total, "HitLine": hit_line}
            (caught if rank <= cutoff else missed).append(entry)
        else:
            unprojected += 1

    caught.sort(key=lambda x: x["Rank"])
    missed.sort(key=lambda x: x["Rank"])
    return {"caught": caught, "missed": missed, "unprojected": unprojected,
            "cutoff": cutoff, "total_ranked": total}


def batter_hits_report(plays: List[Dict], results: Dict[int, Dict], top_n: int = 15) -> Dict:
    """Of batters who got hits, where did the model rank them?"""
    hit_plays = sorted([p for p in plays if p["Market"] == "Batter Total Hits"],
                       key=lambda x: -x["ModelProb"])
    total = len(hit_plays)
    cutoff = max(top_n, int(total * 0.10))
    rank_by_pid = {p.get("PlayerId"): (i + 1, p["ModelProb"], p["Player"], p["Line"])
                   for i, p in enumerate(hit_plays)}

    caught, missed, unprojected = [], [], 0
    for pid, actuals in results.items():
        h_val = actuals.get("hits", 0) or 0
        if h_val < 1:
            continue
        if pid in rank_by_pid:
            rank, prob, name, line = rank_by_pid[pid]
            hit_line = h_val >= line
            entry = {"Player": name, "Hits": h_val, "Line": line, "ModelProb": prob,
                     "Rank": rank, "OfTotal": total, "HitLine": hit_line}
            (caught if rank <= cutoff else missed).append(entry)
        else:
            unprojected += 1

    caught.sort(key=lambda x: x["Rank"])
    missed.sort(key=lambda x: x["Rank"])
    return {"caught": caught, "missed": missed, "unprojected": unprojected,
            "cutoff": cutoff, "total_ranked": total}
