"""Digit statistics, signal rule, backtest and variant scan."""
from dataclasses import dataclass, replace
import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

STRATEGIES = ["over", "under", "even", "odd", "matches", "differs"]


@dataclass(frozen=True)
class Config:
    symbol: str = "R_100"
    strategy: str = "over"
    barrier: int = 2
    window: int = 100
    rule: str = "follow"      # follow: recent rate above expected, revert: below expected
    thr: float = 2.0          # z-score threshold
    margin: float = 0.95      # assumed payout efficiency (about 5% house margin)


def prob(strategy, barrier):
    return {"over": (9 - barrier) / 10, "under": barrier / 10, "even": 0.5,
            "odd": 0.5, "matches": 0.1, "differs": 0.9}[strategy]


def outcome(digits, strategy, barrier):
    d = np.asarray(digits)
    return {"over": d > barrier, "under": d < barrier, "even": d % 2 == 0,
            "odd": d % 2 == 1, "matches": d == barrier, "differs": d != barrier}[strategy]


def label(strategy, barrier):
    return strategy.title() if strategy in ("even", "odd") else f"{strategy.title()} {barrier}"


def profit_on_win(p, margin):
    """Profit per 1 staked if the bet wins, assuming the payout is fair odds times margin."""
    return margin / p - 1


def _signal(z, cfg):
    return z >= cfg.thr if cfg.rule == "follow" else z <= -cfg.thr


def analyse_live(digits, cfg):
    n = cfg.window
    if len(digits) < n:
        return None
    last = np.asarray(digits[-n:])
    counts = np.bincount(last, minlength=10)
    p = prob(cfg.strategy, cfg.barrier)
    obs = float(outcome(last, cfg.strategy, cfg.barrier).mean())
    z = (obs - p) / np.sqrt(p * (1 - p) / n) if 0 < p < 1 else 0.0
    stat = float(((counts - n / 10) ** 2 / (n / 10)).sum())
    run = 1
    while run < len(digits) and digits[-1 - run] == digits[-1]:
        run += 1
    return dict(counts=counts, p=p, obs=obs, z=float(z), chi=stat,
                chi_p=float(chi2.sf(stat, 9)), hot=int(counts.argmax()),
                cold=int(counts.argmin()), run=run,
                signal=bool(0 < p < 1 and _signal(z, cfg)))


def backtest(digits, cfg):
    """Replays the signal rule over history. Signal is read after tick i, trade settles on tick i+1."""
    n, p = cfg.window, prob(cfg.strategy, cfg.barrier)
    if len(digits) <= n + 1 or not 0 < p < 1:
        return None
    w = outcome(digits, cfg.strategy, cfg.barrier).astype(float)
    c = np.concatenate([[0.0], np.cumsum(w)])
    s = (c[n:] - c[:-n])[:-1]                       # outcomes in the n ticks before each trade
    z = (s / n - p) / np.sqrt(p * (1 - p) / n)
    res = w[n:][_signal(z, cfg)]
    t = len(res)
    if t == 0:
        return dict(trades=0, wins=0, win_rate=np.nan, expected=p, pnl=0.0, p_value=np.nan, equity=np.array([]))
    wins = int(res.sum())
    pnl_each = np.where(res == 1, profit_on_win(p, cfg.margin), -1.0)
    zt = (wins - t * p) / np.sqrt(t * p * (1 - p))
    return dict(trades=t, wins=wins, win_rate=wins / t, expected=p, pnl=float(pnl_each.sum()),
                p_value=float(2 * norm.sf(abs(zt))), equity=np.cumsum(pnl_each))


def scan(digits, cfg):
    """Tests many variants of the rule on the same history. The best of many will look good by chance."""
    rows = []
    for rule in ("follow", "revert"):
        for window in (20, 50, 100, 200):
            for thr in (1.0, 1.5, 2.0, 2.5, 3.0):
                r = backtest(digits, replace(cfg, rule=rule, window=window, thr=thr))
                if r and r["trades"] > 0:
                    rows.append(dict(rule=rule, window=window, z_threshold=thr, trades=r["trades"],
                                     win_rate=round(r["win_rate"] * 100, 2), expected=round(r["expected"] * 100, 2),
                                     pnl=round(r["pnl"], 2), p_value=round(r["p_value"], 4)))
    return pd.DataFrame(rows).sort_values("pnl", ascending=False).reset_index(drop=True)
