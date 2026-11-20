
import json
import time
from collections import Counter
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import websocket

st.set_page_config(page_title="DERIV AI PRO", page_icon="📊", layout="wide")

st.title("📊 DERIV AI PRO")
st.caption("Multi-device Deriv digit-analysis prototype • Read-only market data")

st.warning(
    "This version analyses historical ticks only. It does not predict the next tick, "
    "place trades, or guarantee an edge. Keep real-money trading disabled while testing."
)

with st.sidebar:
    st.header("Connection")
    app_id = st.text_input("Deriv App ID", value="", help="Create an app in your Deriv account/API settings and enter its App ID.")
    symbol = st.selectbox(
        "Market",
        ["R_10", "R_25", "R_50", "R_75", "R_100",
         "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"],
        index=0
    )
    count = st.selectbox("Ticks to retrieve", [100, 250, 500, 1000], index=2)
    refresh = st.checkbox("Auto-refresh every 15 seconds", value=False)
    st.caption("Market symbols can vary by account and availability. If a symbol is rejected, choose another supported symbol.")


def fetch_ticks(app_id: str, symbol: str, count: int):
    if not app_id.strip():
        raise ValueError("Enter your Deriv App ID in the sidebar.")
    url = f"wss://ws.derivws.com/websockets/v3?app_id={app_id.strip()}"
    ws = websocket.create_connection(url, timeout=15, suppress_origin=True)
    try:
        req = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "start": 1,
            "style": "ticks"
        }
        ws.send(json.dumps(req))
        deadline = time.time() + 15
        while time.time() < deadline:
            msg = json.loads(ws.recv())
            if "error" in msg:
                raise RuntimeError(msg["error"].get("message", "Deriv API error"))
            if "history" in msg:
                prices = msg["history"].get("prices", [])
                times = msg["history"].get(" times", [])
                pip_size = msg.get("pip_size", 2)
                if not prices:
                    raise RuntimeError("No tick history was returned for this symbol.")
                return prices, times, pip_size
        raise TimeoutError("Timed out waiting for Deriv.")
    finally:
        ws.close()

def last_digit(price, pip_size):
    # Deriv quotes are formatted to the instrument's pip precision.
    decimals = int(pip_size)
    formatted = f"{float(price):.{decimals}f}"
    digits = "".join(ch for ch in formatted if ch.isdigit())
    return int(digits[-1])

def contract_hit_rate(digits, contract, barrier=None, target=None):
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
            prices, times, pip_size = fetch_ticks(app_id, symbol, count)
        digits = [last_digit(p, pip_size) for p in prices]
        st.session_state["analysis"] = {
            "prices": prices, "times": times, "digits": digits,
            "pip_size": pip_size, "symbol": symbol
        }
        st.success(f"Retrieved {len(digits)} ticks for {symbol}.")
    except Exception as e:
        st.error(f"Could not retrieve data: {e}")

data = st.session_state.get("analysis")
if data:
    digits = data["digits"]
    prices = data["prices"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market", data["symbol"])
    c2.metric("Ticks analysed", len(digits))
    c3.metric("Latest quote", str(prices[-1]))
    c4.metric("Latest digit", str(digits[-1]))

    st.subheader("Recent last digits")
    st.write(" ".join(map(str, digits[-50:])))
    st.caption("Displayed in the order returned by the API (oldest to newest).")

    st.subheader("Digit frequency")
    freq = Counter(digits)
    frequency_df = pd.DataFrame({
        "Digit": list(range(10)),
        "Count": [freq.get(i, 0) for i in range(10)],
        "Observed frequency": [freq.get(i, 0) / len(digits) for i in range(10)]
    })
    st.bar_chart(frequency_df.set_index("Digit")["Count"])
    st.dataframe(frequency_df.style.format({"Observed frequency": "{:.1%}"}), use_container_width=True)

    st.subheader("Contract outcome rates in this sample")
    contract = st.selectbox("Contract type", ["Over", "Under", "Matches", "Differs", "Even", "Odd"])
    barrier = None
    target = None
    if contract in ("Over", "Under"):
        barrier = st.slider("Barrier", 0, 9, 2 if contract == "Over" else 8)
    if contract in ("Matches", "Differs"):
        target = st.selectbox("Target digit", list(range(10)), index=7)
    windows = st.columns(3)
    for col, n in zip(windows, [20, 50, 100]):
        sample = digits[-min(n, len(digits)):]
        rate = contract_hit_rate(sample, contract, barrier, target)
        col.metric(f"Last {len(sample)} ticks", f"{rate:.1%}" if rate is not None else "N/A")
    st.info(
        "These are historical sample frequencies, not reliable forecasts of the next tick. "
        "For an independent, uniformly distributed last digit, the baseline rates are "
        "contract-dependent (for example, Over 2 is 70% and Under 8 is 80% before payout/house-edge considerations)."
    )

    st.subheader("Simple strategy comparison")
    rows = []
    for name in ["Over", "Under", "Matches", "Differs", "Even", "Odd"]:
        if name in ("Over", "Under"):
            b = 2 if name == "Over" else 8
            rate = contract_hit_rate(digits, name, barrier=b)
            setting = f"barrier {b}"
        elif name in ("Matches", "Differs"):
            rate = contract_hit_rate(digits, name, target=7)
            setting = "digit 7"
        else:
            rate = contract_hit_rate(digits, name)
            setting = "—"
        rows.append({"Contract": name, "Setting": setting, "Historical hit rate": rate})
    st.dataframe(pd.DataFrame(rows).style.format({"Historical hit rate": "{:.1%}"}), use_container_width=True)

    st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
else:
    st.info("Enter your App ID, select a market, then click **Fetch latest tick history** to begin.")

if refresh:
    st.caption("Auto-refresh is a convenience reminder in this starter build; click Fetch to retrieve a fresh sample.")
