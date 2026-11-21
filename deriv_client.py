"""Deriv WebSocket access (public tick data only) and the paper-trading bot. No API token is used."""
import json
import threading
import time
from collections import deque
from datetime import datetime, timezone

import websocket  # websocket-client

import analysis
import db

WS_URL = "wss://ws.derivws.com/websockets/v3?app_id={app_id}"


def digit_of(quote, pip):
    return int(f"{float(quote):.{int(pip)}f}"[-1])


def fetch_history(symbol, count=5000, app_id="1089"):
    """One-off request for up to 5000 past ticks. Returns a list of last digits."""
    ws = websocket.create_connection(WS_URL.format(app_id=app_id), timeout=15)
    try:
        ws.send(json.dumps({"ticks_history": symbol, "count": count, "end": "latest", "style": "ticks"}))
        msg = json.loads(ws.recv())
    finally:
        ws.close()
    if "error" in msg:
        raise RuntimeError(msg["error"]["message"])
    pip = msg.get("pip_size", 2)
    return [digit_of(p, pip) for p in msg["history"]["prices"]]


class TickFeed:
    """Keeps one live connection open in a background thread and stores recent ticks per symbol."""

    def __init__(self, app_id="1089", maxlen=5000):
        self.app_id, self.maxlen = app_id, maxlen
        self.data, self.pip, self.subs = {}, {}, set()
        self.listeners = []
        self.connected, self.last_error = False, ""
        self._ws = None
        threading.Thread(target=self._run, daemon=True).start()

    # connection ---------------------------------------------------------
    def _run(self):
        while True:
            try:
                self._ws = websocket.WebSocketApp(
                    WS_URL.format(app_id=self.app_id),
                    on_open=self._on_open, on_message=self._on_message,
                    on_error=lambda ws, e: setattr(self, "last_error", str(e)),
                    on_close=lambda *a: setattr(self, "connected", False))
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:  # keep the thread alive
                self.last_error = str(e)
            self.connected = False
            time.sleep(3)

    def _on_open(self, ws):
        self.connected = True
        for s in list(self.subs):
            self._request(s)

    def _request(self, symbol):
        try:
            self._ws.send(json.dumps({"ticks_history": symbol, "count": 1000, "end": "latest",
                                      "style": "ticks", "subscribe": 1}))
        except Exception as e:
            self.last_error = str(e)

    def subscribe(self, symbol):
        if symbol in self.subs:
            return
        self.subs.add(symbol)
        if self.connected:
            self._request(symbol)

    # messages -----------------------------------------------------------
    def _on_message(self, ws, raw):
        m = json.loads(raw)
        if "error" in m:
            self.last_error = m["error"].get("message", "API error")
            return
        if m.get("msg_type") == "history":
            sym = m["echo_req"]["ticks_history"]
            pip = m.get("pip_size", 2)
            self.pip[sym] = pip
            h = m["history"]
            self.data[sym] = deque(((t, float(p), digit_of(p, pip)) for t, p in zip(h["times"], h["prices"])),
                                   maxlen=self.maxlen)
        elif m.get("msg_type") == "tick":
            t = m["tick"]
            sym, pip = t["symbol"], t.get("pip_size", self.pip.get(t["symbol"], 2))
            self.pip[sym] = pip
            row = (t["epoch"], float(t["quote"]), digit_of(t["quote"], pip))
            self.data.setdefault(sym, deque(maxlen=self.maxlen)).append(row)
            for fn in self.listeners:
                fn(sym, *row)

    # reading ------------------------------------------------------------
    def snapshot(self, symbol):
        return list(self.data.get(symbol, []))

    def digits(self, symbol):
        return [r[2] for r in self.snapshot(symbol)]


class PaperBot:
    """Places paper trades when the signal fires and logs each result to SQLite. Never touches real money."""

    def __init__(self, feed, db_path):
        self.feed, self.db_path = feed, db_path
        self.cfg, self.enabled, self.pending = None, False, None
        self._lock = threading.Lock()
        feed.listeners.append(self.on_tick)

    def configure(self, cfg, enabled):
        with self._lock:
            if cfg != self.cfg or enabled != self.enabled:
                self.pending = None
            self.cfg, self.enabled = cfg, enabled

    def on_tick(self, symbol, epoch, quote, digit):
        with self._lock:
            cfg = self.cfg
            if not self.enabled or cfg is None or symbol != cfg.symbol:
                return
            if self.pending is not None:
                p = self.pending
                win = bool(analysis.outcome([digit], p["strategy"], p["barrier"])[0])
                pnl = analysis.profit_on_win(p["p"], cfg.margin) if win else -1.0
                ts = datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")
                db.add_trade(self.db_path, ts, symbol, analysis.label(p["strategy"], p["barrier"]),
                             digit, win, p["p"], pnl)
                self.pending = None
            a = analysis.analyse_live(self.feed.digits(symbol), cfg)
            if a and a["signal"]:
                self.pending = {"strategy": cfg.strategy, "barrier": cfg.barrier, "p": a["p"]}
