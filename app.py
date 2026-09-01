"""
Ledger — Multi-Agent Financial Intelligence Platform
Production build with concurrent 3-agent orchestration, RAG grounding, and persistent portfolio state.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import auth
import db
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import rag
import streamlit as st
import yfinance as yf

# ==========================================
# 1. Page Configuration & Auth
# ==========================================
st.set_page_config(
    layout="wide",
    page_title="Ledger — Financial Intelligence",
    page_icon="◆",
)

auth.init_db()
db.init_db()
retriever = rag.SemanticRetriever()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None

if not st.session_state["logged_in"]:
    st.title("Welcome to Ledger")
    tab1, tab2 = st.tabs(["Login", "Create Account"])

    with tab1:
        with st.form("login_form"):
            st.subheader("Login")
            login_user = st.text_input("Username")
            login_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if auth.verify_user(login_user, login_pass):
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = login_user
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    with tab2:
        with st.form("signup_form"):
            st.subheader("Create Account")
            new_user = st.text_input("Choose Username")
            new_pass = st.text_input("Choose Password", type="password")
            if st.form_submit_button("Sign Up"):
                if new_user and len(new_pass) >= 6:
                    if auth.create_user(new_user, new_pass):
                        st.success("Account created. Please log in.")
                    else:
                        st.error("Username already exists.")
                else:
                    st.warning("Username required; password must be at least 6 characters.")
    st.stop()

# ==========================================
# 2. Design System
# ==========================================
TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {
    --bg: #12100D; --surface: #1C1815; --hairline: #322D27;
    --text: #F0EBE3; --text-muted: #8A8378; --amber: #F2A93B;
    --bull: #4FAE7A; --bear: #D9695F;
}
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: var(--bg); color: var(--text); }
section[data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--hairline); }
.tape { display: flex; flex-wrap: wrap; gap: 0; border: 1px solid var(--hairline); background: var(--surface); margin-bottom: 1.2rem; }
.tape-item { padding: 0.7rem 1.1rem; border-right: 1px solid var(--hairline); font-family: 'IBM Plex Mono', monospace; min-width: 140px; }
.tape-symbol { color: var(--text-muted); font-size: 0.78rem; }
.tape-price { font-size: 1.05rem; font-weight: 600; }
.tape-delta-up { color: var(--bull); font-size: 0.82rem; }
.tape-delta-down { color: var(--bear); font-size: 0.82rem; }
.tape-na { color: var(--text-muted); font-size: 0.82rem; }
.badge { display: inline-block; padding: 0.12rem 0.55rem; border-radius: 2px; font-size: 0.78rem; font-weight: 500; border: 1px solid transparent; }
.badge-bull { color: var(--bull); border-color: var(--bull); background: rgba(79,174,122,0.08); }
.badge-bear { color: var(--bear); border-color: var(--bear); background: rgba(217,105,95,0.08); }
.badge-warn { color: var(--amber); border-color: var(--amber); background: rgba(242,169,59,0.08); }
.badge-neutral { color: var(--text-muted); border-color: var(--hairline); }
table.ledger { width: 100%; border-collapse: collapse; font-family: 'IBM Plex Mono', monospace; font-size: 0.86rem; }
table.ledger th { text-align: left; font-family: 'IBM Plex Sans', sans-serif; font-weight: 500; color: var(--text-muted); font-size: 0.78rem; padding: 0.5rem 0.8rem; border-bottom: 1px solid var(--hairline); }
table.ledger td { padding: 0.55rem 0.8rem; border-bottom: 1px solid var(--hairline); }
.agent-card { border: 1px solid var(--hairline); border-left: 2px solid var(--amber); background: var(--surface); padding: 0.9rem 1.1rem; margin-bottom: 0.6rem; }
.agent-name { font-weight: 600; font-size: 0.92rem; }
.agent-trace { color: var(--text-muted); font-size: 0.88rem; margin-top: 0.3rem; line-height: 1.5; }
.rec-card { border: 1px solid var(--hairline); background: var(--surface); padding: 1.3rem 1.4rem; margin-top: 0.4rem; }
.rec-action { font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem; font-weight: 600; }
.rec-sub { color: var(--text-muted); font-size: 0.9rem; margin-top: 0.2rem; }
.gauge-caption { text-align:center; font-size:0.78rem; color:#8A8378; }
.gauge-stat { text-align:center; font-size:0.72rem; color:#5f5a51; margin-top:-0.4rem; font-family:'IBM Plex Mono', monospace; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ==========================================
# 3. Data Ingestion & Technical Analysis
# ==========================================
def parse_watchlist(raw: str):
    seen, valid, invalid = set(), [], []
    for entry in raw.split(","):
        t = entry.strip().upper()
        if not t:
            continue
        if not TICKER_PATTERN.match(t):
            invalid.append(t)
            continue
        if t not in seen:
            seen.add(t)
            valid.append(t)
    return valid, invalid

def compute_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def compute_macd(closes: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

@st.cache_data(show_spinner=False, ttl=300)
def fetch_market_data(ticker: str, degraded: bool, epoch: int):
    if degraded:
        raise ConnectionError(f"Market feed offline for {ticker}.")
    hist = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=True)
    if hist is None or hist.empty or len(hist) < 30:
        raise ConnectionError(f"Insufficient history for {ticker}.")

    closes = hist["Close"].dropna()
    volumes = hist["Volume"].dropna()
    price = round(float(closes.iloc[-1]), 2)
    prev_price = round(float(closes.iloc[-2]), 2) if len(closes) > 1 else price

    rsi = float(compute_rsi(closes).iloc[-1])
    macd_line, signal_line = compute_macd(closes)
    macd_diff = float(macd_line.iloc[-1] - signal_line.iloc[-1])

    if abs(macd_diff) < 0.0005 * price:
        momentum_label = "Neutral"
    elif macd_diff > 0:
        momentum_label = "Bullish"
    else:
        momentum_label = "Bearish"

    today_volume = float(volumes.iloc[-1])
    avg_vol_20 = float(volumes.tail(21).iloc[:-1].mean()) if len(volumes) > 20 else float(volumes.mean())
    volume_ratio = today_volume / avg_vol_20 if avg_vol_20 > 0 else 1.0
    volume_label = "Anomaly" if volume_ratio >= 1.5 or volume_ratio <= 0.5 else "Standard"

    daily_returns = closes.pct_change().dropna().tail(20)
    annualized_vol_pct = float(daily_returns.std() * (252**0.5) * 100) if len(daily_returns) > 1 else 0.0
    volatility_label = "High" if annualized_vol_pct >= 40 else "Low"

    return {
        "ticker": ticker,
        "price": price,
        "prev_price": prev_price,
        "history": [round(v, 2) for v in closes.tail(24).tolist()],
        "rsi": rsi,
        "macd_diff": macd_diff,
        "volume_ratio": volume_ratio,
        "annualized_vol_pct": annualized_vol_pct,
        "momentum": {"label": momentum_label, "gauge_value": max(0.0, min(100.0, rsi)), "stat": f"RSI {rsi:.0f}"},
        "volume": {
            "label": volume_label,
            "gauge_value": max(0.0, min(100.0, volume_ratio * 50)),
            "stat": f"{volume_ratio:.1f}× 20d avg",
        },
        "volatility": {
            "label": volatility_label,
            "gauge_value": max(0.0, min(100.0, annualized_vol_pct)),
            "stat": f"{annualized_vol_pct:.0f}% ann.",
        },
    }

@st.cache_data(show_spinner=False, ttl=3600)
def fetch_fundamentals(ticker: str, degraded: bool, epoch: int):
    if degraded:
        return None
    try:
        info = yf.Ticker(ticker).get_info()
        return {
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector") or "Unclassified",
            "profit_margin": info.get("profitMargins"),
        }
    except Exception:
        return None

# ==========================================
# 4. Multi-Agent Orchestration & RAG
# ==========================================
def market_agent_task(ticker, market_data, degraded):
    time.sleep(0.15)
    if degraded or market_data is None:
        return {"status": "Degraded", "trace": f"Live telemetry unavailable for {ticker}."}
    return {
        "status": "Success",
        "trace": (
            f"Technical telemetry: RSI(14) at {market_data['rsi']:.1f}; "
            f"MACD spread: {market_data['macd_diff']:+.3f}; "
            f"Volume run-rate: {market_data['volume_ratio']:.1f}× 20-day historical baseline."
        ),
    }

def fundamental_agent_task(ticker, fundamentals, degraded):
    time.sleep(0.15)
    if degraded or fundamentals is None:
        return {"status": "Degraded", "trace": f"Fundamental valuation feed offline for {ticker}."}
    pe = f"{fundamentals['trailing_pe']:.1f}×" if fundamentals.get("trailing_pe") else "N/A"
    mcap = f"${fundamentals['market_cap']/1e9:.1f}B" if fundamentals.get("market_cap") else "N/A"
    return {
        "status": "Success",
        "trace": f"Valuation overview: Sector {fundamentals['sector']}, Trailing P/E {pe}, Capitalization {mcap}.",
    }

def regulatory_rag_agent_task(ticker, degraded):
    time.sleep(0.15)
    if degraded:
        return {"status": "Degraded", "trace": "RAG semantic search index disconnected.", "documents": []}
    docs = retriever.retrieve(f"{ticker} operational risks financial condition disclosure", ticker=ticker, top_k=2)
    if not docs:
        return {"status": "Success", "trace": "No adverse regulatory risk factors flagged.", "documents": []}
    return {
        "status": "Success",
        "trace": f"Grounded retrieval matched {len(docs)} disclosures: {docs[0]['title']} (relevance score {docs[0]['score']}).",
        "documents": docs,
    }

def synthesis_agent_task(ticker, risk_profile, m_res, f_res, r_res, market_data, fundamentals):
    degraded = any(res["status"] == "Degraded" for res in (m_res, f_res, r_res))
    pe_elevated = fundamentals and (fundamentals.get("trailing_pe") or 0) > 45

    if market_data and market_data["momentum"]["label"] == "Bearish":
        action, kind = "REDUCE", "bear"
    elif risk_profile == "Low" and (
        market_data and market_data["volatility"]["label"] == "High" or pe_elevated
    ):
        action, kind = "HOLD", "neutral"
    elif risk_profile == "High" and market_data and market_data["momentum"]["label"] == "Bullish":
        action, kind = "ACCUMULATE", "bull"
    else:
        action, kind = "HOLD", "neutral"

    confidence = 0.50
    if market_data:
        rsi_delta = abs(market_data["rsi"] - 50) / 50
        confidence = min(0.95, max(0.40, 0.40 + (0.40 * rsi_delta) + (0.15 if not degraded else 0.0)))

    attributions = []
    if market_data:
        attributions.append("Yahoo Finance real-time pricing & technicals")
    if fundamentals:
        attributions.append("Corporate financial balance sheet data")
    for doc in r_res.get("documents", []):
        attributions.append(f"{doc['source']} — {doc['title']}")

    rationale = (
        f"Synthesized parallel signals across technical momentum ({market_data['momentum']['label'] if market_data else 'N/A'}), "
        f"valuation profile, and SEC disclosure retrieval. Adapted for a {risk_profile.lower()} risk profile."
    )

    return {
        "action": action,
        "kind": kind,
        "confidence": round(confidence, 2),
        "rationale": rationale,
        "attributions": attributions,
        "degraded_inputs": degraded,
    }

def run_agents(ticker, risk_profile, degraded, market_data, fundamentals):
    start = time.time()
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_market = executor.submit(market_agent_task, ticker, market_data, degraded)
        f_fund = executor.submit(fundamental_agent_task, ticker, fundamentals, degraded)
        f_rag = executor.submit(regulatory_rag_agent_task, ticker, degraded)

        m_res, f_res, r_res = f_market.result(), f_fund.result(), f_rag.result()
    parallel_elapsed = time.time() - start

    synth = synthesis_agent_task(ticker, risk_profile, m_res, f_res, r_res, market_data, fundamentals)
    total_elapsed = time.time() - start

    return {
        "market_agent": m_res,
        "fundamental_agent": f_res,
        "regulatory_rag_agent": r_res,
        "synthesis_agent": synth,
    }, parallel_elapsed, total_elapsed

# ==========================================
# 5. Sidebar & State Control
# ==========================================
if "refresh_epoch" not in st.session_state:
    st.session_state["refresh_epoch"] = 0
if "agent_results" not in st.session_state:
    st.session_state["agent_results"] = {}

if "watchlist_text" not in st.session_state:
    saved = db.get_watchlist(st.session_state["username"])
    if not saved:
        saved = ["AAPL", "TSLA", "NVDA"]
        db.set_watchlist(st.session_state["username"], saved)
    st.session_state["watchlist_text"] = ", ".join(saved)

with st.sidebar:
    st.write(f"Account: **{st.session_state['username']}**")
    if st.button("Log out"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = None
        st.rerun()

    st.divider()
    st.markdown("**User Risk Profile**")
    risk_profile = st.selectbox("Risk Profile", ["Low", "Medium", "High"], index=1)

    watchlist_input = st.text_input("Active Watchlist", st.session_state["watchlist_text"])
    watchlist, invalid_tickers = parse_watchlist(watchlist_input)

    if invalid_tickers:
        st.caption(f"Invalid entries: {', '.join(invalid_tickers)}")

    if watchlist != db.get_watchlist(st.session_state["username"]):
        if st.button("Save Watchlist"):
            db.set_watchlist(st.session_state["username"], watchlist)
            st.session_state["watchlist_text"] = ", ".join(watchlist)
            st.success("Watchlist updated.")
            st.rerun()

    st.divider()
    st.markdown("**Simulation & Feeds**")
    simulate_degraded = st.toggle("Simulate Data Feed Outage", False)
    if st.button("Refresh Live Telemetry"):
        st.session_state["refresh_epoch"] += 1
        st.session_state["agent_results"] = {}
        fetch_market_data.clear()
        fetch_fundamentals.clear()
        st.rerun()

# ==========================================
# 6. Primary Tabs
# ==========================================
tab_dash, tab_port, tab_hist, tab_arch = st.tabs(["Dashboard", "Portfolio", "History", "Architecture"])

def signal_badge(label, kind):
    return f'<span class="badge badge-{kind}">{label}</span>'

with tab_dash:
    st.title("Ledger Multi-Agent Financial Intelligence")

    if not watchlist:
        st.info("Please specify one or more tickers in the sidebar.")
    else:
        tape_html = ['<div class="tape">']
        snapshot = {}
        for t in watchlist:
            try:
                data = fetch_market_data(t, simulate_degraded, st.session_state["refresh_epoch"])
                snapshot[t] = data
                diff = data["price"] - data["prev_price"]
                cls = "tape-delta-up" if diff >= 0 else "tape-delta-down"
                arrow = "▲" if diff >= 0 else "▼"
                tape_html.append(
                    f'<div class="tape-item"><div class="tape-symbol">{t}</div>'
                    f'<div class="tape-price">${data["price"]:.2f}</div>'
                    f'<div class="{cls}">{arrow} {abs(diff):.2f}</div></div>'
                )
            except Exception:
                snapshot[t] = None
                tape_html.append(
                    f'<div class="tape-item"><div class="tape-symbol">{t}</div>'
                    f'<div class="tape-price">--</div><div class="tape-na">offline</div></div>'
                )
        tape_html.append("</div>")
        st.markdown("".join(tape_html), unsafe_allow_html=True)

        st.subheader("Market Signal Overview")
        rows = [
            "<table class='ledger'><tr><th>Ticker</th><th>Price</th><th>Momentum</th><th>Volume</th><th>Volatility</th></tr>"
        ]
        for t in watchlist:
            d = snapshot[t]
            if d is None:
                rows.append(f"<tr><td>{t}</td><td colspan='4'>Feed degraded</td></tr>")
                continue
            rows.append(
                f"<tr><td>{t}</td><td>${d['price']:.2f}</td>"
                f"<td>{signal_badge(d['momentum']['label'], 'bull' if d['momentum']['label']=='Bullish' else 'bear' if d['momentum']['label']=='Bearish' else 'neutral')}</td>"
                f"<td>{signal_badge(d['volume']['label'], 'warn' if d['volume']['label']=='Anomaly' else 'neutral')}</td>"
                f"<td>{signal_badge(d['volatility']['label'], 'warn' if d['volatility']['label']=='High' else 'bull')}</td></tr>"
            )
        rows.append("</table>")
        st.markdown("".join(rows), unsafe_allow_html=True)

        st.divider()

        selected_ticker = st.selectbox("Select Asset for Multi-Agent Analysis", watchlist)
        sel_market = snapshot.get(selected_ticker)
        sel_fund = fetch_fundamentals(selected_ticker, simulate_degraded, st.session_state["refresh_epoch"])

        if sel_market:
            c1, c2 = st.columns([1.3, 1])
            with c1:
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        y=sel_market["history"],
                        mode="lines",
                        line=dict(color="#F2A93B", width=2),
                        fill="tozeroy",
                        fillcolor="rgba(242,169,59,0.08)",
                    )
                )
                fig.update_layout(
                    height=200,
                    margin=dict(l=5, r=5, t=5, b=5),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            with c2:
                gc1, gc2, gc3 = st.columns(3)
                for col, title, val, stat in [
                    (gc1, "Momentum", sel_market["momentum"]["gauge_value"], sel_market["momentum"]["stat"]),
                    (gc2, "Volume", sel_market["volume"]["gauge_value"], sel_market["volume"]["stat"]),
                    (gc3, "Volatility", sel_market["volatility"]["gauge_value"], sel_market["volatility"]["stat"]),
                ]:
                    gfig = go.Figure(
                        go.Indicator(
                            mode="gauge+number",
                            value=val,
                            number={"font": {"size": 15, "color": "#F0EBE3"}},
                            gauge={"axis": {"range": [0, 100], "visible": False}, "bar": {"color": "#F2A93B"}},
                        )
                    )
                    gfig.update_layout(height=100, margin=dict(l=5, r=5, t=5, b=0), paper_bgcolor="rgba(0,0,0,0)")
                    col.markdown(f"<div class='gauge-caption'>{title}</div>", unsafe_allow_html=True)
                    col.plotly_chart(gfig, use_container_width=True, config={"displayModeBar": False})
                    col.markdown(f"<div class='gauge-stat'>{stat}</div>", unsafe_allow_html=True)

        if st.button(f"Execute Multi-Agent Reasoning Swarm on {selected_ticker}", type="primary"):
            with st.status("Executing concurrent agents...", expanded=True) as status:
                st.write("Dispatched Market, Fundamental, and Regulatory RAG agents concurrently.")
                results, par_time, total_time = run_agents(
                    selected_ticker, risk_profile, simulate_degraded, sel_market, sel_fund
                )
                st.write(f"All 3 agents returned in {par_time:.2f}s. Synthesis layer applied.")
                status.update(label=f"Analysis completed in {total_time:.2f}s", state="complete")

            st.session_state["agent_results"][selected_ticker] = {
                "results": results,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            db.add_analysis_record(
                st.session_state["username"], selected_ticker, risk_profile, results["synthesis_agent"], total_time
            )

        stored = st.session_state["agent_results"].get(selected_ticker)
        if stored:
            res = stored["results"]
            st.caption(f"Analysis completed at {stored['timestamp']}")

            for name, key in [
                ("Market Dynamics Agent", "market_agent"),
                ("Fundamental Analysis Agent", "fundamental_agent"),
                ("Regulatory RAG Agent", "regulatory_rag_agent"),
            ]:
                ag = res[key]
                st.markdown(
                    f'<div class="agent-card"><span class="agent-name">△ {name}</span> '
                    f'{signal_badge(ag["status"], "bull" if ag["status"]=="Success" else "warn")}'
                    f'<div class="agent-trace">{ag["trace"]}</div></div>',
                    unsafe_allow_html=True,
                )

            synth = res["synthesis_agent"]
            st.markdown(
                f'<div class="rec-card">'
                f'<div class="rec-action badge-{synth["kind"]}">{synth["action"]} {selected_ticker}</div>'
                f'<div class="rec-sub">{synth["confidence"]*100:.0f}% confidence · {risk_profile} Risk Allocation</div>'
                f'<div class="agent-trace" style="margin-top:0.6rem;">{synth["rationale"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("**Grounded Attribution & Sources:**")
            if len(synth["attributions"]) > 0:
                for attr in synth["attributions"]:
                    st.markdown(f"- {attr}")
            else:
                st.markdown("- No citations generated.")

with tab_port:
    st.title("Portfolio Tracking & P/L")
    with st.form("add_holding_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        h_ticker = c1.text_input("Asset Ticker")
        h_shares = c2.number_input("Shares", min_value=0.01, step=1.0)
        h_cost = c3.number_input("Cost Basis / Share ($)", min_value=0.0, step=0.1)
        if st.form_submit_button("Add Position"):
            t = h_ticker.strip().upper()
            if t and TICKER_PATTERN.match(t):
                db.add_holding(st.session_state["username"], t, h_shares, h_cost if h_cost > 0 else None)
                st.success(f"Position recorded: {h_shares} {t}")
                st.rerun()
            else:
                st.error("Invalid ticker symbol.")

    holdings = db.get_holdings(st.session_state["username"])
    if holdings:
        total_val, total_cost = 0.0, 0.0
        p_rows = [
            "<table class='ledger'><tr><th>Ticker</th><th>Shares</th><th>Cost/Sh</th><th>Price</th><th>Value</th><th>P/L</th></tr>"
        ]
        for h in holdings:
            try:
                md = fetch_market_data(h["ticker"], simulate_degraded, st.session_state["refresh_epoch"])
                curr_p = md["price"]
            except Exception:
                curr_p = 0.0
            val = h["shares"] * curr_p
            total_val += val
            cost = (h["cost_basis"] or 0) * h["shares"]
            total_cost += cost
            pl = val - cost if h["cost_basis"] else 0.0
            p_rows.append(
                f"<tr><td>{h['ticker']}</td><td>{h['shares']}</td><td>${(h['cost_basis'] or 0):.2f}</td>"
                f"<td>${curr_p:.2f}</td><td>${val:,.2f}</td><td>${pl:+,.2f}</td></tr>"
            )
        p_rows.append("</table>")
        st.markdown("".join(p_rows), unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        m1.metric("Portfolio Valuation", f"${total_val:,.2f}")
        m2.metric("Total Basis", f"${total_cost:,.2f}")
        m3.metric("Unrealized P/L", f"${total_val - total_cost:+,.2f}")

        for h in holdings:
            del_c1, del_c2 = st.columns([5, 1])
            del_c1.write(f"{h['ticker']} ({h['shares']} shares)")
            if del_c2.button("Delete", key=f"del_{h['id']}"):
                db.delete_holding(st.session_state["username"], h["id"])
                st.rerun()

with tab_hist:
    st.title("Historical Agent Invocations")
    history = db.get_history(st.session_state["username"])
    if history:
        for item in history:
            with st.expander(
                f"{item['run_at'][:19]} — {item['ticker']} — {item['action']} ({item['confidence']*100:.0f}%) — {item.get('latency', 0):.2f}s latency"
            ):
                st.write(item["rationale"])
                st.markdown("**Citations:**")
                if len(item["attributions"]) > 0:
                    for att in item["attributions"]:
                        st.markdown(f"- {att}")
                else:
                    st.markdown("- No citations generated.")
    else:
        st.info("No prior agent executions recorded.")

with tab_arch:
    st.title("System Architecture")
    st.markdown(
        """
- **Parallel Swarm**: Orchestrates 3 concurrent agents (`MarketAgent`, `FundamentalAgent`, `RegulatoryRAGAgent`) via `ThreadPoolExecutor`.
- **RAG & Vector Semantic Search**: TF-IDF cosine-similarity retrieval pipeline indexing regulatory disclosures and risk factors.
- **Persistence**: SQLite database managing hashed credentials, positions, execution latency tracking, and analysis history across sessions.
"""
    )