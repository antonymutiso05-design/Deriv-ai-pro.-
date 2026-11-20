import json, math
from collections import Counter
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import websocket

WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
st.set_page_config(page_title="DERIV AI PRO", page_icon="📊", layout="wide")

@st.cache_data(ttl=300)
def get_markets():
    ws = websocket.create_connection(WS_URL, timeout=20)
    try:
        ws.send(json.dumps({"active_symbols":"brief","req_id":1}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("msg_type") == "active_symbols":
                return msg.get("active_symbols", [])
            if msg.get("error"):
                raise RuntimeError(msg["error"].get("message","Deriv API error"))
    finally:
        ws.close()

def get_history(symbol, count):
    ws = websocket.create_connection(WS_URL, timeout=25)
    try:
        ws.send(json.dumps({"ticks_history":symbol,"count":int(count),"end":"latest","style":"ticks","req_id":2}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("msg_type") == "history":
                h = msg.get("history", {})
                prices, times = h.get("prices", []), h.get("times", [])
                if not prices: raise RuntimeError("No historical ticks returned.")
                return prices, times, msg.get("pip_size")
            if msg.get("error"):
                raise RuntimeError(msg["error"].get("message","Deriv API error"))
    finally:
        ws.close()

def decimals_for(pip_size, prices):
    if pip_size:
        try:
            return max(0, min(10, int(round(-math.log10(float(pip_size))))))
        except Exception:
            pass
    places = []
    for price in prices:
        value = str(price)
        places.append(len(value.split(".", 1)[1].rstrip("0")) if "." in value else 0)
    return min(10, max(places, default=0))

def digit_of(price, decimals):
    s = f"{float(price):.{decimals}f}"
    return int(s[-1]) if s[-1].isdigit() else 0

def test_rule(digits, rule, target):
    wins = []
    for i in range(len(digits)-1):
        d = digits[i+1]
        if rule == "Over": ok = d > target
        elif rule == "Under": ok = d < target
        elif rule == "Matches": ok = d == target
        elif rule == "Differs": ok = d != target
        elif rule == "Even": ok = d % 2 == 0
        else: ok = d % 2 == 1
        wins.append(ok)
    return wins

st.title("📊 DERIV AI PRO")
st.caption("All active Deriv markets • Digit statistics • Historical backtesting")
st.warning("Analysis only: this app does not place trades. Historical hit rates do not predict or guarantee future outcomes.")

with st.sidebar:
    st.header("Market selection")
    if st.button("Refresh markets"): get_markets.clear()
    try: markets = [m for m in get_markets() if m.get("symbol")]
    except Exception as e:
        st.error(f"Could not load markets: {e}")
        st.stop()
    labels = [f'{m.get("display_name",m["symbol"])} ({m["symbol"]}) — {m.get("market_display_name",m.get("market","Other"))}' for m in markets]
    selected_index = st.selectbox(
    "All available active markets",
    range(len(markets)),
    format_func=lambda i: labels[i]
)

market = markets[selected_index]
symbol = market["symbol"]
    count = st.select_slider("Historical ticks", options=[20,50,100,200,500,1000], value=100)
    rule = st.selectbox("Strategy to test", ["Over","Under","Matches","Differs","Even","Odd"])
    target = st.selectbox("Target digit / threshold", list(range(10)), index=5)

if st.button("Load market data and run analysis", type="primary"):
    with st.spinner(f"Loading historical data for {symbol}..."):
        try:
            prices, times, pip = get_history(symbol, count)
            places = decimals_for(pip, prices)
            digits = [digit_of(p, places) for p in prices]
            df = pd.DataFrame({
                "Time": [datetime.fromtimestamp(int(t),tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S") for t in times],
                "Price": [float(p) for p in prices],
                "Digit": digits
            })
            st.session_state["df"] = df
            st.session_state["symbol"] = symbol
            st.session_state["places"] = places
            st.session_state["digits"] = digits
        except Exception as e:
            st.error(f"Could not retrieve data: {e}")

if "df" not in st.session_state:
    st.info("Choose a market, tick count and strategy, then select **Load market data and run analysis**.")
    st.write(f"Currently available active symbols returned by Deriv: **{len(markets)}**")
    st.stop()

df, digits = st.session_state["df"], st.session_state["digits"]
freq, n = Counter(digits), len(digits)
st.subheader(f'Market: {st.session_state["symbol"]}')
a,b,c,d = st.columns(4)
a.metric("Ticks loaded", n)
b.metric("Decimal places", st.session_state["places"])
c.metric("Most frequent digit", freq.most_common(1)[0][0] if freq else "—")
d.metric("Latest digit", digits[-1] if digits else "—")

left,right = st.columns(2)
with left:
    st.markdown("### Digit frequency")
    fdf = pd.DataFrame({"Digit":range(10),"Count":[freq.get(i,0) for i in range(10)],"Percentage":[round(freq.get(i,0)/n*100,2) if n else 0 for i in range(10)]})
    st.bar_chart(fdf.set_index("Digit")["Count"])
    st.dataframe(fdf,hide_index=True,use_container_width=True)
with right:
    st.markdown("### Latest 20 ticks")
    st.dataframe(df.tail(20).iloc[::-1],hide_index=True,use_container_width=True)

st.markdown("### Historical strategy backtest")
st.caption("Each observed digit is tested against the next historical tick. This is a one-step hit-rate test, not a contract payout or profitability simulation.")
wins_list = test_rule(digits, rule, target)
if wins_list:
    wins, total = sum(wins_list), len(wins_list)
    rate = wins/total*100
    x,y,z,q = st.columns(4)
    x.metric("Strategy",rule)
    y.metric("Tests",total)
    z.metric("Wins / losses",f"{wins} / {total-wins}")
    q.metric("Historical hit rate",f"{rate:.2f}%")
    st.progress(rate/100)
else: st.warning("At least two ticks are required for backtesting.")

st.markdown("### Compare all six strategies")
rows=[]
for name in ["Over","Under","Matches","Differs","Even","Odd"]:
    result=test_rule(digits,name,target)
    total=len(result); w=sum(result)
    rows.append({"Strategy":name,"Wins":w,"Losses":total-w,"Hit rate (%)":round(w/total*100,2) if total else 0})
st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
st.markdown("### Recent digit sequence")
st.code("  ".join(map(str,digits[-50:])))
