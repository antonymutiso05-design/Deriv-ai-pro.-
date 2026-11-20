
import json
import time
from collections import Counter
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import websocket

st.set_page_config(page_title="DERIV AI PRO", page_icon="📊", layout="wide")
st.title("📊 DERIV AI PRO")
st.caption("Multi-device Deriv digit-analysis prototype • Read-only public market data")
st.warning("This version analyses historical ticks only. It does not predict the next tick, place trades, or guarantee an edge. Keep real-money trading disabled while testing.")

with st.sidebar:
    st.header("Market settings")
    st.caption("Public market data connection — no App ID or API token required.")
    symbol = st.selectbox("Market", ["R_10", "R_25", "R_50", "R_75", "R_100", "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"])
    count = st.selectbox("Ticks to retrieve", [100, 250, 500, 1000], index=2)

def fetch_ticks(symbol: str, count: int):
    url = "wss://api.derivws.com/trading/v1/options/ws/public"
    ws = websocket.create_connection(url, timeout=15, suppress_origin=True)
    try:
        ws.send(json.dumps({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "start": 1,
            "style": "ticks",
            "req_id": 1
        }))
        deadline = time.time() + 15
        while time.time() < deadline:
            msg = json.loads(ws.recv())
            if "error" in msg:
                raise RuntimeError(msg["error"].get("message", "Deriv API error"))
            if "history" in msg:
                prices = msg["history"].get("prices", [])
                times = msg["history"].get("times", [])
                pip_size = msg.get("pip_size", 2)
                if not prices:
                    raise RuntimeError("No tick history was returned for this symbol.")
                return prices, times, pip_size
        raise TimeoutError("Timed out waiting for Deriv.")
    finally:
        ws.close()

def last_digit(price, pip_size):
    formatted = f"{float(price):.{int(pip_size)}f}"
    digits = "".join(ch for ch in formatted if ch.isdigit())
    return int(digits[-1])

def hit_rate(digits, contract, barrier=None, target=None):
    if not digits:
        return None
    if contract == "Over":
        return sum(d > barrier for d in digits) / len(digits)
    if contract == "Under":
        return sum(d < barrier for d in digits) / len(digits)
    if contract == "Matches":
        return sum(d == target for d in digits) / len(digits)
    if contract == "Differs":
        return sum(d != target for d in digits) / len(digits)
    if contract == "Even":
        return sum(d % 2 == 0 for d in digits) / len(digits)
    if contract == "Odd":
        return sum(d % 2 == 1 for d in digits) / len(digits)
    return None

if st.button("Fetch latest tick history", type="primary"):
    try:
        with st.spinner("Connecting to Deriv and retrieving ticks..."):
            prices, times, pip_size = fetch_ticks(symbol, count)
        digits = [last_digit(p, pip_size) for p in prices]
        st.session_state["analysis"] = {"prices": prices, "times": times, "digits": digits, "pip_size": pip_size, "symbol": symbol}
        st.success(f"Retrieved {len(digits)} ticks for {symbol}.")
    except Exception as e:
        st.error(f"Could not retrieve data: {e}")

data = st.session_state.get("analysis")
if data:
    digits, prices = data["digits"], data["prices"]
    a, b, c, d = st.columns(4)
    a.metric("Market", data["symbol"])
    b.metric("Ticks analysed", len(digits))
    c.metric("Latest quote", str(prices[-1]))
    d.metric("Latest digit", str(digits[-1]))

    st.subheader("Recent last digits")
    st.write(" ".join(map(str, digits[-50:])))
    st.caption("Digits are displayed oldest to newest.")

    st.subheader("Digit frequency")
    freq = Counter(digits)
    df = pd.DataFrame({"Digit": range(10), "Count": [freq.get(i, 0) for i in range(10)], "Observed frequency": [freq.get(i, 0) / len(digits) for i in range(10)]})
    st.bar_chart(df.set_index("Digit")["Count"])
    st.dataframe(df.style.format({"Observed frequency": "{:.1%}"}), use_container_width=True)

    st.subheader("Contract outcome rates in this sample")
    contract = st.selectbox("Contract type", ["Over", "Under", "Matches", "Differs", "Even", "Odd"])
    barrier = st.slider("Barrier", 0, 9, 2 if contract == "Over" else 8) if contract in ("Over", "Under") else None
    target = st.selectbox("Target digit", list(range(10)), index=7) if contract in ("Matches", "Differs") else None
    cols = st.columns(3)
    for col, n in zip(cols, [20, 50, 100]):
        sample = digits[-min(n, len(digits)):]
        rate = hit_rate(sample, contract, barrier, target)
        col.metric(f"Last {len(sample)} ticks", f"{rate:.1%}")
    st.info("These are historical sample frequencies, not reliable forecasts of the next tick. A past frequency does not establish an advantage or account for contract payouts.")

    st.subheader("Strategy sample comparison")
    rows = []
    for name in ["Over", "Under", "Matches", "Differs", "Even", "Odd"]:
        if name in ("Over", "Under"):
            setting = "barrier 2" if name == "Over" else "barrier 8"
            rate = hit_rate(digits, name, 2 if name == "Over" else 8)
        elif name in ("Matches", "Differs"):
            setting, rate = "digit 7", hit_rate(digits, name, target=7)
        else:
            setting, rate = "—", hit_rate(digits, name)
        rows.append({"Contract": name, "Setting": setting, "Historical hit rate": rate})
    st.dataframe(pd.DataFrame(rows).style.format({"Historical hit rate": "{:.1%}"}), use_container_width=True)
    st.caption(f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
else:
    st.info("Select a market and click **Fetch latest tick history** to begin. Public market data does not require an App ID or API token.")
