"""Deriv Digit Analyser (Streamlit). Run with: streamlit run app.py"""
import numpy as np
import pandas as pd
import streamlit as st

import analysis
import db
from analysis import Config
from deriv_client import PaperBot, TickFeed, fetch_history

DB_PATH = "deriv_trades.db"
SYMBOLS = {
    "Volatility 10 Index": "R_10", "Volatility 25 Index": "R_25", "Volatility 50 Index": "R_50",
    "Volatility 75 Index": "R_75", "Volatility 100 Index": "R_100",
    "Volatility 10 (1s) Index": "1HZ10V", "Volatility 15 (1s) Index": "1HZ15V",
    "Volatility 25 (1s) Index": "1HZ25V", "Volatility 30 (1s) Index": "1HZ30V",
    "Volatility 50 (1s) Index": "1HZ50V", "Volatility 75 (1s) Index": "1HZ75V",
    "Volatility 90 (1s) Index": "1HZ90V", "Volatility 100 (1s) Index": "1HZ100V",
}

st.set_page_config(page_title="Deriv Digit Analyser", layout="wide")


@st.cache_resource
def get_runtime(app_id):
    feed = TickFeed(app_id)
    return feed, PaperBot(feed, DB_PATH)


# ---------- sidebar ----------
with st.sidebar:
    st.header("Settings")
    app_id = st.text_input("Deriv app ID", "1089", help="1089 is Deriv's public test ID. Use your own when you have one.")
    name = st.selectbox("Market", list(SYMBOLS), index=4)
    strategy = st.selectbox("Strategy", analysis.STRATEGIES)
    if strategy == "over":
        barrier = st.selectbox("Barrier digit", range(0, 9), index=2)
    elif strategy == "under":
        barrier = st.selectbox("Barrier digit", range(1, 10), index=7)
    elif strategy in ("matches", "differs"):
        barrier = st.selectbox("Digit", range(0, 10), index=5)
    else:
        barrier = 0
    window = st.selectbox("Last digits analysed", [20, 50, 100, 200, 500], index=2)
    rule = st.radio("Signal rule", ["follow", "revert"], horizontal=True,
                    format_func=lambda r: "Rate above expected" if r == "follow" else "Rate below expected")
    thr = st.slider("Z-score threshold", 0.5, 4.0, 2.0, 0.5)
    margin = st.slider("Assumed payout efficiency", 0.90, 1.00, 0.95, 0.01,
                       help="0.95 assumes about a 5% house margin. Deriv's platform shows exact payouts.")
    bot_on = st.toggle("Run paper-trading bot", value=False)
    st.caption("Paper trades use fake money. Nothing here can place a real trade.")

cfg = Config(SYMBOLS[name], strategy, int(barrier), int(window), rule, float(thr), float(margin))
feed, bot = get_runtime(app_id.strip() or "1089")
feed.subscribe(cfg.symbol)
bot.configure(cfg, bot_on)

st.title("Deriv Digit Analyser")
tab_live, tab_back, tab_hist = st.tabs(["Live", "Backtest", "Paper trade history"])


# ---------- live ----------
@st.fragment(run_every=1)
def live():
    rows = feed.snapshot(cfg.symbol)
    st.caption(("Connected" if feed.connected else "Connecting") + f" | {feed.url.split('?')[0]}" +
               (f" | {feed.last_error[:120]}" if feed.last_error and not feed.connected else ""))
    if len(rows) < cfg.window:
        st.info(f"Collecting ticks: {len(rows)} of {cfg.window}")
        return
    digits = [r[2] for r in rows]
    a = analysis.analyse_live(digits, cfg)
    pip = feed.pip.get(cfg.symbol, 2)

    c1, c2 = st.columns([1, 1])
    c1.metric("Latest tick", f"{rows[-1][1]:.{pip}f}")
    c2.metric("Signal (paper only)", "BUY" if a["signal"] else "WAIT")

    chips = "".join(
        f"<span style='display:inline-block;width:34px;height:40px;line-height:40px;text-align:center;margin:0 5px 5px 0;"
        f"border:1px solid {'#1b7f79' if analysis.outcome([d], cfg.strategy, cfg.barrier)[0] else '#888'};border-radius:6px;"
        f"font:600 18px monospace'>{d}</span>" for d in digits[-20:])
    st.markdown("**Last 20 digits** (green outline = would have won)")
    st.markdown(chips, unsafe_allow_html=True)

    freq = pd.DataFrame({"frequency %": a["counts"] / cfg.window * 100}, index=pd.Index(range(10), name="digit"))
    st.markdown(f"**Digit frequency, last {cfg.window}** (expected 10% each; hot {a['hot']}, cold {a['cold']})")
    st.bar_chart(freq, height=240)

    m = st.columns(4)
    m[0].metric(f"{analysis.label(cfg.strategy, cfg.barrier)} expected", f"{a['p'] * 100:.0f}%")
    m[1].metric(f"Observed, last {cfg.window}", f"{a['obs'] * 100:.1f}%")
    m[2].metric("Z score", f"{a['z']:.2f}")
    m[3].metric("Repeat streak", f"{digits[-1]} x{a['run']}" if a["run"] > 1 else "none")
    verdict = "Digits look consistent with random" if a["chi_p"] >= 0.05 else "Distribution deviates from uniform (check again on fresh data)"
    st.caption(f"Chi-square randomness test: p = {a['chi_p']:.3f}. {verdict}.")


with tab_live:
    live()


# ---------- backtest ----------
with tab_back:
    st.write("Replays the current signal rule on up to 5,000 past ticks. Each signal places a trade on the next tick.")
    if st.button("Run backtest"):
        try:
            st.session_state["hist"] = (cfg.symbol, fetch_history(cfg.symbol, 5000, app_id.strip() or "1089"))
        except Exception as e:
            st.error(f"Could not fetch history: {e}")
    sym, hist = st.session_state.get("hist", (None, None))
    if hist:
        st.caption(f"{len(hist)} ticks of {sym}")
        r = analysis.backtest(hist, cfg)
        if r is None or r["trades"] == 0:
            st.warning("No trades triggered. Lower the threshold or use a shorter window.")
        else:
            m = st.columns(5)
            m[0].metric("Trades", r["trades"])
            m[1].metric("Win rate", f"{r['win_rate'] * 100:.1f}%")
            m[2].metric("Expected", f"{r['expected'] * 100:.1f}%")
            m[3].metric("Paper profit", f"{r['pnl']:.1f}")
            m[4].metric("p-value", f"{r['p_value']:.3f}")
            st.line_chart(pd.DataFrame({"cumulative profit": r["equity"]}))
            st.caption("The p-value tests whether the win rate differs from chance. Even a low value needs fresh data to confirm.")
        if st.button("Scan 40 rule variants"):
            table = analysis.scan(hist, cfg)
            st.dataframe(table, use_container_width=True)
            st.caption(f"With 40 variants, about {40 * 0.05:.0f} will show p < 0.05 by luck alone, and the top row will usually look "
                       "profitable. Re-test the top rule on new ticks before believing it.")


# ---------- history ----------
with tab_hist:
    df = db.load_trades(DB_PATH)
    if df.empty:
        st.info("No paper trades yet. Turn on the paper-trading bot in the sidebar and wait for BUY signals.")
    else:
        t, w, exp = len(df), int(df["win"].sum()), float(df["p"].mean())
        z = (w - t * exp) / np.sqrt(t * exp * (1 - exp)) if 0 < exp < 1 else 0.0
        m = st.columns(4)
        m[0].metric("Trades", t)
        m[1].metric("Win rate", f"{w / t * 100:.1f}%")
        m[2].metric("Expected", f"{exp * 100:.1f}%")
        m[3].metric("Paper profit", f"{df['pnl'].sum():.2f}")
        st.line_chart(pd.DataFrame({"cumulative profit": df["pnl"].cumsum()}))
        st.dataframe(df.iloc[::-1], use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        c1.download_button("Download CSV", df.to_csv(index=False), "paper_trades.csv", "text/csv")
        if c2.button("Clear history"):
            db.clear_trades(DB_PATH)
            st.rerun()
