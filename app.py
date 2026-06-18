import streamlit as st
import streamlit.components.v1 as components
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
import feedparser
import requests
import html
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Margin Manor Terminal V75",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# AUTO-REFRESH / CACHE SETTINGS
# ============================================================

# The clock below updates every second in the browser.
# Market data is intentionally cached separately to avoid hammering free/delayed APIs.
DEFAULT_AUTO_REFRESH_SECONDS = 60
MARKET_DATA_CACHE_TTL_SECONDS = 60
NEWS_CACHE_TTL_SECONDS = 300
CALENDAR_CACHE_TTL_SECONDS = 300


# ============================================================
# BLOOMBERG-INSPIRED DENSE TERMINAL CSS
# ============================================================

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: "Courier New", monospace;
        font-size: 13px;
    }

    .stApp {
        background-color: #000000;
        color: #f2f2f2;
    }

    header[data-testid="stHeader"] {
        background-color: #000000;
    }

    .block-container {
        padding-top: 0.55rem;
        padding-bottom: 3.3rem;
        max-width: 1780px;
    }

    section[data-testid="stSidebar"] {
        background-color: #050505;
        border-right: 1px solid #2b2b2b;
    }

    h1 {
        color: #ffb000;
        letter-spacing: 1px;
        font-size: 1.9rem;
        margin-bottom: 0.1rem;
    }

    h2, h3 {
        color: #ffb000;
        letter-spacing: 0.3px;
        margin-top: 0.45rem;
        margin-bottom: 0.35rem;
    }

    .terminal-subtitle {
        color: #aaaaaa;
        font-size: 0.78rem;
        margin-bottom: 0.35rem;
    }

    .function-bar {
        background: linear-gradient(90deg, #171000, #050505 55%, #171000);
        border: 1px solid #ffb000;
        color: #ffb000;
        padding: 8px 10px;
        margin-bottom: 8px;
        font-weight: bold;
        font-size: 0.9rem;
    }

    .terminal-panel {
        background-color: #070707;
        border: 1px solid #2e2e2e;
        border-radius: 2px;
        padding: 8px;
        margin-bottom: 8px;
        box-shadow: 0px 0px 9px rgba(255, 176, 0, 0.04);
    }

    .terminal-panel-title {
        color: #ffb000;
        font-size: 0.82rem;
        font-weight: bold;
        margin-bottom: 5px;
        border-bottom: 1px solid #303030;
        padding-bottom: 4px;
    }

    .terminal-small {
        color: #aaaaaa;
        font-size: 0.72rem;
    }

    .metric-box {
        background-color: #070707;
        border: 1px solid #333333;
        border-radius: 2px;
        padding: 8px;
        min-height: 74px;
        margin-bottom: 8px;
    }

    .metric-title {
        color: #ffb000;
        font-size: 0.7rem;
        margin-bottom: 3px;
        text-transform: uppercase;
    }

    .metric-value {
        color: #ffffff;
        font-size: 1.15rem;
        font-weight: bold;
        line-height: 1.1;
    }

    .metric-note {
        color: #aaaaaa;
        font-size: 0.68rem;
        margin-top: 3px;
    }

    .positive { color: #00ff99; }
    .negative { color: #ff4d4d; }
    .neutral { color: #ffb000; }
    .danger { color: #ff4d4d; font-weight: bold; }
    .success { color: #00ff99; font-weight: bold; }
    .warning { color: #ffb000; font-weight: bold; }
    .dim { color: #777777; }

    .tape-container {
        width: 100%;
        overflow: hidden;
        background-color: #050505;
        border-top: 1px solid #333333;
        border-bottom: 1px solid #333333;
        padding: 6px 0;
        margin-bottom: 8px;
        white-space: nowrap;
    }

    .tape {
        display: inline-block;
        animation: ticker 48s linear infinite;
        font-size: 0.78rem;
    }

    .tape-item {
        margin-right: 25px;
        font-weight: bold;
    }

    @keyframes ticker {
        0% { transform: translateX(0%); }
        100% { transform: translateX(-50%); }
    }

    .news-card {
        background-color: #080808;
        border: 1px solid #303030;
        border-left: 3px solid #ffb000;
        border-radius: 2px;
        padding: 8px;
        margin-bottom: 7px;
    }

    .news-source {
        color: #ffb000;
        font-size: 0.68rem;
    }

    .news-title {
        color: #ffffff;
        font-weight: bold;
        margin-top: 3px;
        margin-bottom: 3px;
        font-size: 0.78rem;
    }

    .alert-card {
        background-color: #140707;
        border: 1px solid #552222;
        border-left: 3px solid #ff4d4d;
        border-radius: 2px;
        padding: 7px;
        margin-bottom: 6px;
        color: #ffffff;
        font-size: 0.74rem;
    }

    .good-alert-card {
        background-color: #061008;
        border: 1px solid #225533;
        border-left: 3px solid #00ff99;
        border-radius: 2px;
        padding: 7px;
        margin-bottom: 6px;
        color: #ffffff;
        font-size: 0.74rem;
    }

    .warning-alert-card {
        background-color: #161005;
        border: 1px solid #554000;
        border-left: 3px solid #ffb000;
        border-radius: 2px;
        padding: 7px;
        margin-bottom: 6px;
        color: #ffffff;
        font-size: 0.74rem;
    }

    .status-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #050505;
        border-top: 1px solid #ffb000;
        color: #ffb000;
        padding: 6px 12px;
        z-index: 9999;
        font-size: 0.72rem;
        white-space: nowrap;
    }

    .command-help {
        color: #aaaaaa;
        font-size: 0.72rem;
        line-height: 1.35;
    }

    div[data-testid="stMetricLabel"] { color: #ffb000; }
    div[data-testid="stMetricValue"] { color: #ffffff; }
    div[data-testid="stMetricDelta"] { font-size: 0.78rem; }

    .stTextInput input, .stTextArea textarea {
        background-color: #030303;
        color: #ffb000;
        border: 1px solid #ffb000;
        font-family: "Courier New", monospace;
    }

    .stSelectbox div, .stMultiSelect div, .stNumberInput input {
        font-family: "Courier New", monospace;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #2a2a2a;
    }

    a { color: #ffb000 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# TERMINAL CONSTANTS
# ============================================================

DEFAULT_WATCHLIST = (
    "SPY, QQQ, DIA, IWM, ^GSPC, ^NDX, ^DJI, ^RUT, "
    "XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC, "
    "GLD, SLV, GC=F, SI=F, GDX, GDXJ, USO, UNG, CL=F, NG=F, HG=F, "
    "TLT, IEF, SHY, HYG, LQD, TIP, ^IRX, ^FVX, ^TNX, ^TYX, "
    "UUP, DX-Y.NYB, EURUSD=X, GBPUSD=X, USDJPY=X, USDCHF=X, USDCAD=X, AUDUSD=X, NZDUSD=X, EURJPY=X, GBPJPY=X, EURGBP=X, "
    "BTC-USD, ETH-USD, SOL-USD, BNB-USD, XRP-USD, ^VIX, ^VIX3M, VXX, "
    "AAPL, MSFT, NVDA, TSLA, AMZN, META, GOOGL, JPM, BAC, GS, XOM, CVX, "
    "^FTSE, ^GDAXI, ^FCHI, ^N225, ^HSI, 000001.SS"
)

ASSET_GROUPS = {
    "EQUITIES / INDICES": ["SPY", "QQQ", "DIA", "IWM", "^GSPC", "^NDX", "^DJI", "^RUT"],
    "US SECTORS": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"],
    "MEGA CAP / SINGLE STOCKS": ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "JPM", "BAC", "GS", "XOM", "CVX"],
    "RATES / CREDIT": ["^IRX", "^FVX", "^TNX", "^TYX", "SHY", "IEF", "TLT", "TIP", "HYG", "LQD"],
    "FX / USD": ["DX-Y.NYB", "UUP", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X", "AUDUSD=X", "NZDUSD=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X"],
    "COMMODITIES": ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F", "GLD", "SLV", "USO", "UNG", "GDX", "GDXJ"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "VOLATILITY": ["^VIX", "^VIX3M", "VXX"],
    "GLOBAL INDICES": ["^FTSE", "^GDAXI", "^FCHI", "^N225", "^HSI", "000001.SS"],
}

CHART_UNIVERSE = {
    "Core Market": ["SPY", "QQQ", "DIA", "IWM", "^GSPC", "^NDX", "^DJI", "^RUT", "^VIX"],
    "Gold / Metals": ["GC=F", "SI=F", "GLD", "SLV", "GDX", "GDXJ", "XAUUSD=X", "XAGUSD=X"],
    "FX": ["DX-Y.NYB", "UUP", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X", "AUDUSD=X", "NZDUSD=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X"],
    "Rates / Bonds": ["^IRX", "^FVX", "^TNX", "^TYX", "SHY", "IEF", "TLT", "TIP", "HYG", "LQD"],
    "Commodities": ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F", "USO", "UNG"],
    "Mega Cap": ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "JPM", "BAC", "GS", "XOM", "CVX"],
    "US Sectors": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"],
    "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "Global Indices": ["^FTSE", "^GDAXI", "^FCHI", "^N225", "^HSI", "000001.SS"],
}

MACRO_TICKERS = {
    "3M Yield Proxy": "^IRX",
    "5Y Yield Proxy": "^FVX",
    "10Y Yield Proxy": "^TNX",
    "30Y Yield Proxy": "^TYX",
    "US Dollar Index Proxy": "DX-Y.NYB",
    "Dollar ETF": "UUP",
    "Gold Futures": "GC=F",
    "Silver Futures": "SI=F",
    "Copper Futures": "HG=F",
    "Crude Oil Futures": "CL=F",
    "Natural Gas Futures": "NG=F",
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "Dow Jones": "^DJI",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
    "VIX 3M": "^VIX3M",
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
}

FUNCTION_SCREENS = [
    "MMKT <GO> Market Command Center",
    "GP <GO> Charts",
    "DES <GO> Security Description",
    "RV <GO> Relative Value",
    "XAU <GO> Gold Cockpit",
    "RATES <GO> Yield Curve",
    "MACRO <GO> Macro Dashboard",
    "CN <GO> News Intelligence",
    "ECO <GO> Economic Calendar",
    "ALRT <GO> Alert Deck",
    "PORT <GO> Portfolio Risk",
    "EQSC <GO> Screener",
    "CORR <GO> Correlation",
    "MAP <GO> Asset Map",
    "HELP <GO> Function Directory",
]

FUNCTION_ALIAS_TO_SCREEN = {
    "MM": FUNCTION_SCREENS[0], "MMKT": FUNCTION_SCREENS[0], "HOME": FUNCTION_SCREENS[0], "RISK": FUNCTION_SCREENS[0],
    "GP": FUNCTION_SCREENS[1], "CHART": FUNCTION_SCREENS[1], "G": FUNCTION_SCREENS[1],
    "DES": FUNCTION_SCREENS[2], "SEC": FUNCTION_SCREENS[2], "QUOTE": FUNCTION_SCREENS[2],
    "RV": FUNCTION_SCREENS[3], "RELVAL": FUNCTION_SCREENS[3], "COMPARE": FUNCTION_SCREENS[3],
    "XAU": FUNCTION_SCREENS[4], "GOLD": FUNCTION_SCREENS[4],
    "RATES": FUNCTION_SCREENS[5], "YC": FUNCTION_SCREENS[5], "YCRV": FUNCTION_SCREENS[5],
    "MACRO": FUNCTION_SCREENS[6], "WEI": FUNCTION_SCREENS[6],
    "CN": FUNCTION_SCREENS[7], "NEWS": FUNCTION_SCREENS[7], "TOP": FUNCTION_SCREENS[7],
    "ECO": FUNCTION_SCREENS[8], "ECON": FUNCTION_SCREENS[8], "CAL": FUNCTION_SCREENS[8],
    "ALRT": FUNCTION_SCREENS[9], "ALERT": FUNCTION_SCREENS[9], "ALERTS": FUNCTION_SCREENS[9],
    "PORT": FUNCTION_SCREENS[10], "PORTFOLIO": FUNCTION_SCREENS[10], "RISKPORT": FUNCTION_SCREENS[10],
    "EQSC": FUNCTION_SCREENS[11], "SCREEN": FUNCTION_SCREENS[11], "SCR": FUNCTION_SCREENS[11],
    "CORR": FUNCTION_SCREENS[12], "CORREL": FUNCTION_SCREENS[12],
    "MAP": FUNCTION_SCREENS[13], "ASSET": FUNCTION_SCREENS[13], "HEATMAP": FUNCTION_SCREENS[13],
    "HELP": FUNCTION_SCREENS[14], "MENU": FUNCTION_SCREENS[14], "?": FUNCTION_SCREENS[14],
}

ASSET_CLASS_MAP = {
    "equity": ["SPY", "QQQ", "DIA", "IWM", "^GSPC", "^NDX", "^DJI", "^RUT", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"],
    "rates_credit": ["^IRX", "^FVX", "^TNX", "^TYX", "SHY", "IEF", "TLT", "TIP", "HYG", "LQD"],
    "fx": ["DX-Y.NYB", "UUP", "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X", "AUDUSD=X", "NZDUSD=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X"],
    "commodity": ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F", "GLD", "SLV", "USO", "UNG", "GDX", "GDXJ"],
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "volatility": ["^VIX", "^VIX3M", "VXX"],
}

# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    try:
        return float(value)
    except Exception:
        return np.nan


def color_value(value):
    try:
        value = float(value)
        if value > 0:
            return "color: #00ff99"
        if value < 0:
            return "color: #ff4d4d"
        return "color: #ffffff"
    except Exception:
        return "color: #ffffff"


def color_impact(value):
    value = str(value)
    if value in ["Red", "High"]:
        return "color: #ff4d4d; font-weight: bold"
    if value in ["Orange", "Medium"]:
        return "color: #ffb000; font-weight: bold"
    if value in ["Yellow", "Low"]:
        return "color: #ffff66; font-weight: bold"
    return "color: #ffffff"


def pct_class(value):
    try:
        value = float(value)
        if value > 0:
            return "positive"
        if value < 0:
            return "negative"
        return "neutral"
    except Exception:
        return "neutral"


def format_signed_pct(value):
    try:
        value = float(value)
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"
    except Exception:
        return "N/A"


def format_number(value, decimals=2):
    try:
        value = float(value)
        if abs(value) >= 1_000_000_000:
            return f"{value/1_000_000_000:.2f}B"
        if abs(value) >= 1_000_000:
            return f"{value/1_000_000:.2f}M"
        if abs(value) >= 1_000:
            return f"{value:,.{decimals}f}"
        return f"{value:.{decimals}f}"
    except Exception:
        return "N/A"


def flatten_yfinance_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def terminal_box(title, value, note="", css_class="neutral"):
    st.markdown(
        f"""
        <div class="metric-box">
            <div class="metric-title">{html.escape(str(title))}</div>
            <div class="metric-value {css_class}">{html.escape(str(value))}</div>
            <div class="metric-note">{html.escape(str(note))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_card(text, kind="warning"):
    if kind == "good":
        css = "good-alert-card"
    elif kind == "danger":
        css = "alert-card"
    else:
        css = "warning-alert-card"
    st.markdown(f'<div class="{css}">{html.escape(str(text))}</div>', unsafe_allow_html=True)


def classify_asset(ticker):
    ticker = str(ticker).upper()
    for cls, members in ASSET_CLASS_MAP.items():
        if ticker in [m.upper() for m in members]:
            return cls.replace("_", " /").title()
    if ticker.endswith("=X"):
        return "Fx"
    if ticker.endswith("-USD"):
        return "Crypto"
    return "Single Stock / Other"


def normalize_to_100(df):
    clean = df.dropna(how="all").ffill().dropna()
    if clean.empty:
        return clean
    first = clean.iloc[0].replace(0, np.nan)
    return clean.divide(first).multiply(100)


def live_sgt_clock_html(label="SGT LIVE"):
    return f"""
    <div style="
        background: linear-gradient(90deg, #171000, #050505 55%, #171000);
        border: 1px solid #ffb000;
        color: #ffb000;
        padding: 8px 10px;
        margin-bottom: 8px;
        font-family: 'Courier New', monospace;
        font-weight: bold;
        font-size: 0.9rem;
        white-space: nowrap;
    ">
        {html.escape(label)} <span id="live-sgt-clock">--</span>
    </div>
    <script>
    function updateLiveSgtClock() {{
        const now = new Date();
        const formatted = new Intl.DateTimeFormat('en-GB', {{
            timeZone: 'Asia/Singapore',
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        }}).format(now).replace(',', '');
        document.getElementById('live-sgt-clock').textContent = formatted;
    }}
    updateLiveSgtClock();
    setInterval(updateLiveSgtClock, 1000);
    </script>
    """


# ============================================================
# DATA FUNCTIONS
# ============================================================

@st.cache_data(ttl=MARKET_DATA_CACHE_TTL_SECONDS, show_spinner=False)
def get_price_data(ticker, period, interval):
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if df.empty:
            return pd.DataFrame()
        df = flatten_yfinance_columns(df)
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=MARKET_DATA_CACHE_TTL_SECONDS, show_spinner=False)
def build_watchlist(tickers, period, interval):
    rows = []
    price_series = {}

    for ticker in tickers:
        df = get_price_data(ticker, period, interval)
        if df.empty or "Close" not in df.columns:
            continue
        df = df.dropna(subset=["Close"])
        if len(df) < 2:
            continue

        close = df["Close"].dropna()
        last = safe_float(close.iloc[-1])
        previous = safe_float(close.iloc[-2])
        if np.isnan(last) or np.isnan(previous) or previous == 0:
            continue

        change = last - previous
        change_pct = (last / previous - 1) * 100
        five_period_pct = (last / safe_float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else np.nan
        twenty_period_pct = (last / safe_float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else np.nan
        returns = close.pct_change().dropna()
        ann_vol = returns.std() * np.sqrt(252) * 100 if len(returns) > 2 else np.nan

        if "Volume" in df.columns:
            volume = df["Volume"].dropna()
            last_volume = safe_float(volume.iloc[-1]) if not volume.empty else np.nan
            avg_volume = safe_float(volume.tail(20).mean()) if len(volume) >= 1 else np.nan
            volume_ratio = last_volume / avg_volume if avg_volume and not np.isnan(avg_volume) and avg_volume != 0 else np.nan
        else:
            last_volume = np.nan
            avg_volume = np.nan
            volume_ratio = np.nan

        ma20 = safe_float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else np.nan
        ma50 = safe_float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else np.nan
        ma200 = safe_float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else np.nan
        dist_ma20 = (last / ma20 - 1) * 100 if ma20 and not np.isnan(ma20) else np.nan
        dist_ma50 = (last / ma50 - 1) * 100 if ma50 and not np.isnan(ma50) else np.nan
        dist_ma200 = (last / ma200 - 1) * 100 if ma200 and not np.isnan(ma200) else np.nan

        if not np.isnan(dist_ma20) and not np.isnan(dist_ma50):
            if dist_ma20 > 0 and dist_ma50 > 0:
                trend = "Bullish"
            elif dist_ma20 < 0 and dist_ma50 < 0:
                trend = "Bearish"
            else:
                trend = "Mixed"
        else:
            trend = "N/A"

        rolling_high = safe_float(close.tail(20).max()) if len(close) >= 5 else np.nan
        rolling_low = safe_float(close.tail(20).min()) if len(close) >= 5 else np.nan
        drawdown_20 = (last / rolling_high - 1) * 100 if rolling_high and not np.isnan(rolling_high) else np.nan

        rows.append({
            "Ticker": ticker,
            "Asset Class": classify_asset(ticker),
            "Last": round(last, 4),
            "Change": round(change, 4),
            "Change %": round(change_pct, 2),
            "5-Period %": round(five_period_pct, 2) if not np.isnan(five_period_pct) else None,
            "20-Period %": round(twenty_period_pct, 2) if not np.isnan(twenty_period_pct) else None,
            "Ann. Vol %": round(ann_vol, 2) if not np.isnan(ann_vol) else None,
            "Volume Ratio": round(volume_ratio, 2) if not np.isnan(volume_ratio) else None,
            "Dist. 20MA %": round(dist_ma20, 2) if not np.isnan(dist_ma20) else None,
            "Dist. 50MA %": round(dist_ma50, 2) if not np.isnan(dist_ma50) else None,
            "Dist. 200MA %": round(dist_ma200, 2) if not np.isnan(dist_ma200) else None,
            "20P High": round(rolling_high, 4) if not np.isnan(rolling_high) else None,
            "20P Low": round(rolling_low, 4) if not np.isnan(rolling_low) else None,
            "20P Drawdown %": round(drawdown_20, 2) if not np.isnan(drawdown_20) else None,
            "Trend": trend,
            "Avg Volume": round(avg_volume, 0) if not np.isnan(avg_volume) else None,
        })
        price_series[ticker] = close.rename(ticker)

    watchlist_df = pd.DataFrame(rows)
    prices_df = pd.DataFrame(price_series).dropna(how="all") if price_series else pd.DataFrame()
    return watchlist_df, prices_df


@st.cache_data(ttl=MARKET_DATA_CACHE_TTL_SECONDS, show_spinner=False)
def get_macro_proxy_data(macro_tickers, period, interval):
    rows = []
    prices = {}

    for label, ticker in macro_tickers.items():
        df = get_price_data(ticker, period, interval)
        if df.empty or "Close" not in df.columns:
            continue
        df = df.dropna(subset=["Close"])
        if len(df) < 2:
            continue
        close = df["Close"].dropna()
        last_raw = safe_float(close.iloc[-1])
        previous_raw = safe_float(close.iloc[-2])
        if np.isnan(last_raw) or np.isnan(previous_raw) or previous_raw == 0:
            continue

        display_last = last_raw / 10 if ticker in ["^IRX", "^FVX", "^TNX", "^TYX"] else last_raw
        display_previous = previous_raw / 10 if ticker in ["^IRX", "^FVX", "^TNX", "^TYX"] else previous_raw
        change = display_last - display_previous
        change_pct = (last_raw / previous_raw - 1) * 100
        five_period_pct = (last_raw / safe_float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else np.nan
        twenty_period_pct = (last_raw / safe_float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else np.nan

        rows.append({
            "Macro Driver": label,
            "Ticker": ticker,
            "Latest": round(display_last, 4),
            "Change": round(change, 4),
            "Change %": round(change_pct, 2),
            "5-Period %": round(five_period_pct, 2) if not np.isnan(five_period_pct) else None,
            "20-Period %": round(twenty_period_pct, 2) if not np.isnan(twenty_period_pct) else None,
        })
        prices[label] = (close / 10).rename(label) if ticker in ["^IRX", "^FVX", "^TNX", "^TYX"] else close.rename(label)

    summary_df = pd.DataFrame(rows)
    price_df = pd.DataFrame(prices).dropna(how="all") if prices else pd.DataFrame()
    return summary_df, price_df


@st.cache_data(ttl=NEWS_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_rss_news(max_items=120):
    feed_urls = [
        ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
        ("CNBC Markets", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("Google Markets", "https://news.google.com/rss/search?q=financial+markets&hl=en-US&gl=US&ceid=US:en"),
        ("Google Fed", "https://news.google.com/rss/search?q=Federal+Reserve+markets+stocks+bonds&hl=en-US&gl=US&ceid=US:en"),
        ("Google Economy", "https://news.google.com/rss/search?q=economy+inflation+stocks+bonds+commodities&hl=en-US&gl=US&ceid=US:en"),
        ("Google Gold", "https://news.google.com/rss/search?q=gold+prices+dollar+yields&hl=en-US&gl=US&ceid=US:en"),
        ("Google Oil", "https://news.google.com/rss/search?q=oil+prices+markets+inflation&hl=en-US&gl=US&ceid=US:en"),
        ("Google Crypto", "https://news.google.com/rss/search?q=crypto+bitcoin+markets&hl=en-US&gl=US&ceid=US:en"),
    ]
    rows = []
    for source, url in feed_urls:
        try:
            response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                continue
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                published = entry.get("published", "")
                if title:
                    rows.append({"Source": source, "Published": published, "Headline": title, "Link": link})
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()
    return df.drop_duplicates(subset=["Headline"]).head(max_items)


@st.cache_data(ttl=CALENDAR_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_forexfactory_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    rows = []
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return pd.DataFrame()
        root = ET.fromstring(response.content)
        for event in root.findall(".//event"):
            def get_text(tag):
                node = event.find(tag)
                return str(node.text).strip() if node is not None and node.text is not None else ""
            title = get_text("title")
            if not title:
                continue
            rows.append({
                "Date": get_text("date"),
                "Time": get_text("time"),
                "Currency": get_text("country"),
                "Impact": get_text("impact"),
                "Event": title,
                "Actual": get_text("actual"),
                "Forecast": get_text("forecast"),
                "Previous": get_text("previous"),
                "URL": get_text("url"),
            })
    except Exception:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["Impact"] = df["Impact"].replace({"High": "Red", "Medium": "Orange", "Low": "Yellow", "Holiday": "Low", "Non-Economic": "Low"})
    return df


def parse_ff_datetime_to_singapore(date_text, time_text, source_timezone="America/New_York"):
    try:
        if not date_text or not time_text:
            return "", "", "N/A", pd.NaT
        time_clean = str(time_text).strip()
        if time_clean.lower() in ["all day", "tentative", ""]:
            return date_text, time_clean, "N/A", pd.NaT
        event_dt = datetime.strptime(f"{date_text} {time_clean}", "%m-%d-%Y %I:%M%p")
        source_dt = event_dt.replace(tzinfo=ZoneInfo(source_timezone))
        sg_dt = source_dt.astimezone(ZoneInfo("Asia/Singapore"))
        now_sg = datetime.now(ZoneInfo("Asia/Singapore"))
        total_minutes = int((sg_dt - now_sg).total_seconds() // 60)
        if total_minutes < 0:
            countdown = "Passed"
        else:
            countdown = f"{total_minutes // 60}h {total_minutes % 60}m"
        return sg_dt.strftime("%Y-%m-%d"), sg_dt.strftime("%H:%M"), countdown, sg_dt
    except Exception:
        return date_text, time_text, "N/A", pd.NaT


def build_forexfactory_display(df, currencies=None, impacts=None, source_timezone="America/New_York"):
    if df is None or df.empty:
        return pd.DataFrame()
    display_rows = []
    for _, row in df.iterrows():
        currency = str(row.get("Currency", ""))
        impact = str(row.get("Impact", ""))
        if currencies and currency not in currencies:
            continue
        if impacts and impact not in impacts:
            continue
        sg_date, sg_time, countdown, sg_dt = parse_ff_datetime_to_singapore(str(row.get("Date", "")), str(row.get("Time", "")), source_timezone)
        display_rows.append({
            "SG Date": sg_date,
            "SG Time": sg_time,
            "Countdown": countdown,
            "Currency": currency,
            "Impact": impact,
            "Event": row.get("Event", ""),
            "Actual": row.get("Actual", ""),
            "Forecast": row.get("Forecast", ""),
            "Previous": row.get("Previous", ""),
            "Source URL": row.get("URL", ""),
            "SG Datetime": sg_dt,
        })
    display_df = pd.DataFrame(display_rows)
    if display_df.empty:
        return display_df
    impact_rank = {"Red": 1, "Orange": 2, "Yellow": 3, "Low": 4}
    display_df["Impact Rank"] = display_df["Impact"].map(impact_rank).fillna(9)
    display_df = display_df.sort_values(["SG Date", "SG Time", "Impact Rank"]).drop(columns=["Impact Rank"])
    return display_df

# ============================================================
# ANALYTICS
# ============================================================

def parse_command(command):
    raw = str(command or "").strip()
    cleaned = raw.replace("<GO>", " ").replace(" GO", " ").strip()
    parts = [p for p in cleaned.split() if p]
    result = {
        "raw": raw,
        "function": "MMKT",
        "screen": FUNCTION_SCREENS[0],
        "ticker": None,
        "tickers": [],
        "keyword": "",
        "message": "Type HELP <GO> for the function directory.",
    }
    if not parts:
        return result

    fn = parts[0].upper()
    result["function"] = fn
    result["screen"] = FUNCTION_ALIAS_TO_SCREEN.get(fn, FUNCTION_SCREENS[14])

    if fn in ["GP", "CHART", "DES", "SEC", "QUOTE"] and len(parts) >= 2:
        result["ticker"] = parts[1].upper()
        result["tickers"] = [result["ticker"]]
    elif fn in ["RV", "RELVAL", "COMPARE", "CORR", "CORREL"] and len(parts) >= 2:
        result["tickers"] = [p.upper() for p in parts[1:]]
        result["ticker"] = result["tickers"][0] if result["tickers"] else None
    elif fn in ["NEWS", "CN", "TOP", "SCREEN", "SCR", "EQSC"]:
        result["keyword"] = " ".join(parts[1:]).strip()
    elif fn in ["XAU", "GOLD"]:
        result["ticker"] = "GC=F"
        result["tickers"] = ["GC=F", "DX-Y.NYB", "^TNX", "^VIX"]
    elif fn == "HELP":
        pass
    elif fn not in FUNCTION_ALIAS_TO_SCREEN:
        result["message"] = f"Unknown function {fn}. Try HELP <GO>."
        return result

    if result["screen"] != FUNCTION_SCREENS[14]:
        extra = ""
        if result["ticker"]:
            extra = f" | ACTIVE TICKER: {result['ticker']}"
        elif result["tickers"]:
            extra = f" | ACTIVE SET: {', '.join(result['tickers'])}"
        elif result["keyword"]:
            extra = f" | FILTER: {result['keyword']}"
        result["message"] = f"{fn} <GO> loaded{extra}."
    return result


def get_row_change(df, ticker):
    if df is None or df.empty or "Ticker" not in df.columns or "Change %" not in df.columns:
        return None
    match = df[df["Ticker"] == ticker]
    if match.empty:
        return None
    try:
        return float(match.iloc[0]["Change %"])
    except Exception:
        return None


def get_change_pct_from_tables(watchlist_df, macro_summary_df, ticker=None, label=None):
    try:
        if ticker and watchlist_df is not None and not watchlist_df.empty:
            match = watchlist_df[watchlist_df["Ticker"] == ticker]
            if not match.empty:
                return float(match.iloc[0]["Change %"])
        if ticker and macro_summary_df is not None and not macro_summary_df.empty:
            match = macro_summary_df[macro_summary_df["Ticker"] == ticker]
            if not match.empty:
                return float(match.iloc[0]["Change %"])
        if label and macro_summary_df is not None and not macro_summary_df.empty:
            match = macro_summary_df[macro_summary_df["Macro Driver"] == label]
            if not match.empty:
                return float(match.iloc[0]["Change %"])
    except Exception:
        return np.nan
    return np.nan


def compute_risk_regime(watchlist_df, macro_summary_df):
    score = 0
    signals = []

    def lookup(ticker):
        value = get_row_change(watchlist_df, ticker)
        return value if value is not None else get_row_change(macro_summary_df, ticker)

    spy = lookup("SPY")
    qqq = lookup("QQQ")
    vix = lookup("^VIX")
    dollar = lookup("UUP") if lookup("UUP") is not None else lookup("DX-Y.NYB")
    btc = lookup("BTC-USD")
    tlt = lookup("TLT")
    oil = lookup("CL=F")

    if spy is not None:
        score += 1 if spy > 0 else -1
        signals.append("SPY positive: equity risk appetite supportive." if spy > 0 else "SPY negative: broad equity pressure.")
    if qqq is not None:
        score += 1 if qqq > 0 else -1
        signals.append("QQQ positive: growth risk appetite supportive." if qqq > 0 else "QQQ negative: growth/tech pressure.")
    if vix is not None:
        score += 1 if vix < 0 else -1
        signals.append("VIX falling: fear cooling." if vix < 0 else "VIX rising: fear increasing.")
    if dollar is not None:
        score += 1 if dollar < 0 else -1
        signals.append("Dollar softer: easier cross-asset conditions." if dollar < 0 else "Dollar stronger: tighter cross-asset pressure.")
    if btc is not None:
        score += 1 if btc > 0 else -1
        signals.append("Bitcoin positive: speculative liquidity present." if btc > 0 else "Bitcoin negative: speculative liquidity weaker.")
    if tlt is not None and spy is not None:
        if spy < 0 and tlt > 0:
            score -= 1
            signals.append("Stocks down while TLT up: defensive bond bid.")
        elif spy > 0 and tlt < 0:
            score += 1
            signals.append("Stocks up while TLT down: risk-on rotation.")
        else:
            signals.append("TLT signal mixed relative to equities.")
    if oil is not None:
        if oil > 1:
            signals.append("Oil up strongly: inflation impulse watch.")
        elif oil < -1:
            signals.append("Oil down strongly: growth/inflation concern watch.")

    if score >= 3:
        return "RISK-ON", "success", score, signals
    if score <= -3:
        return "RISK-OFF", "danger", score, signals
    return "MIXED / TRANSITION", "warning", score, signals


def compute_xau_command_score(watchlist_df, macro_summary_df):
    driver_specs = [
        {"Driver": "Gold Futures", "Ticker": "GC=F", "Label": "Gold Futures", "Weight": 3, "Bullish When Up": True, "Logic": "Gold itself rising is direct XAU strength."},
        {"Driver": "Silver Futures", "Ticker": "SI=F", "Label": "Silver Futures", "Weight": 1, "Bullish When Up": True, "Logic": "Silver rising confirms precious metals demand."},
        {"Driver": "US Dollar", "Ticker": "UUP", "Label": "Dollar ETF", "Weight": 2, "Bullish When Up": False, "Logic": "A stronger USD is usually a headwind for gold."},
        {"Driver": "DXY Proxy", "Ticker": "DX-Y.NYB", "Label": "US Dollar Index Proxy", "Weight": 2, "Bullish When Up": False, "Logic": "DXY strength usually pressures USD-priced gold."},
        {"Driver": "10Y Yield", "Ticker": "^TNX", "Label": "10Y Yield Proxy", "Weight": 2, "Bullish When Up": False, "Logic": "Higher yields usually raise opportunity cost for gold."},
        {"Driver": "30Y Yield", "Ticker": "^TYX", "Label": "30Y Yield Proxy", "Weight": 1, "Bullish When Up": False, "Logic": "Higher long-end yields can pressure gold."},
        {"Driver": "VIX", "Ticker": "^VIX", "Label": "VIX", "Weight": 1, "Bullish When Up": True, "Logic": "Rising fear can create safe-haven demand for gold."},
        {"Driver": "Nasdaq 100", "Ticker": "^NDX", "Label": "Nasdaq 100", "Weight": 1, "Bullish When Up": False, "Logic": "Strong risk appetite can reduce defensive gold demand."},
        {"Driver": "Bitcoin", "Ticker": "BTC-USD", "Label": "Bitcoin", "Weight": 1, "Bullish When Up": True, "Logic": "Bitcoin strength can signal speculative liquidity."},
        {"Driver": "Oil", "Ticker": "CL=F", "Label": "Crude Oil Futures", "Weight": 1, "Bullish When Up": True, "Logic": "Oil strength can support inflation-sensitive commodity demand."},
        {"Driver": "Copper", "Ticker": "HG=F", "Label": "Copper Futures", "Weight": 1, "Bullish When Up": True, "Logic": "Copper can reflect commodity/growth impulse."},
    ]
    rows = []
    total_score = 0
    for spec in driver_specs:
        change_pct = get_change_pct_from_tables(watchlist_df, macro_summary_df, ticker=spec["Ticker"], label=spec["Label"])
        if np.isnan(change_pct):
            contribution = 0
            effect = "Missing"
        else:
            if change_pct > 0:
                contribution = spec["Weight"] if spec["Bullish When Up"] else -spec["Weight"]
            elif change_pct < 0:
                contribution = -spec["Weight"] if spec["Bullish When Up"] else spec["Weight"]
            else:
                contribution = 0
            effect = "Tailwind" if contribution > 0 else "Headwind" if contribution < 0 else "Neutral"
        total_score += contribution
        rows.append({
            "Driver": spec["Driver"],
            "Ticker": spec["Ticker"],
            "Change %": round(change_pct, 2) if not np.isnan(change_pct) else None,
            "Weight": spec["Weight"],
            "Contribution": contribution,
            "Effect on XAU": effect,
            "Logic": spec["Logic"],
        })
    total_score = max(min(total_score, 10), -10)
    if total_score >= 4:
        bias = "BULLISH XAU TAILWIND"
        action = "Macro supports gold. Wait for bullish price confirmation before entry."
    elif total_score <= -4:
        bias = "BEARISH XAU HEADWIND"
        action = "Macro pressures gold. Wait for bearish price confirmation before entry."
    else:
        bias = "MIXED / WAIT"
        action = "Macro is not clean. Wait for clearer driver alignment."
    return total_score, bias, action, pd.DataFrame(rows)


def build_event_risk_score(calendar_df):
    if calendar_df is None or calendar_df.empty:
        return 0, "NO CALENDAR DATA", pd.DataFrame()
    active = calendar_df.copy()
    if "Countdown" in active.columns:
        active = active[active["Countdown"] != "Passed"]
    score = 0
    for _, row in active.iterrows():
        impact = str(row.get("Impact", ""))
        if impact == "Red":
            score += 3
        elif impact == "Orange":
            score += 2
        elif impact == "Yellow":
            score += 1
    if score >= 10:
        regime = "EXTREME EVENT RISK"
    elif score >= 6:
        regime = "HIGH EVENT RISK"
    elif score >= 3:
        regime = "MODERATE EVENT RISK"
    else:
        regime = "LOW EVENT RISK"
    return score, regime, active


def get_next_high_impact_event(calendar_df):
    if calendar_df is None or calendar_df.empty:
        return "N/A"
    active = calendar_df[calendar_df.get("Countdown", "") != "Passed"].copy()
    active = active[active["Impact"].isin(["Red", "Orange"])]
    if active.empty:
        return "No upcoming red/orange event"
    row = active.iloc[0]
    return f"{row['Currency']} {row['Impact']} | {row['SG Date']} {row['SG Time']} | {row['Event']}"


def build_ticker_tape(watchlist_df):
    if watchlist_df is None or watchlist_df.empty:
        return ""
    items = []
    for _, row in watchlist_df.head(36).iterrows():
        ticker = row.get("Ticker", "")
        change = row.get("Change %", np.nan)
        cls = pct_class(change)
        items.append(f'<span class="tape-item {cls}">{html.escape(str(ticker))} {format_signed_pct(change)}</span>')
    tape = "".join(items) * 2
    return f'<div class="tape-container"><div class="tape">{tape}</div></div>'


def create_candlestick_chart(df, ticker, height=520):
    fig = go.Figure()
    if df is None or df.empty:
        return fig
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name=ticker))
    if len(df) >= 20:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"].rolling(20).mean(), mode="lines", name="20 MA"))
    if len(df) >= 50:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"].rolling(50).mean(), mode="lines", name="50 MA"))
    if len(df) >= 200:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"].rolling(200).mean(), mode="lines", name="200 MA"))
    fig.update_layout(
        template="plotly_dark",
        title=f"GP <GO> {ticker}",
        height=height,
        xaxis_rangeslider_visible=False,
        margin=dict(l=15, r=15, t=40, b=15),
        paper_bgcolor="#000000",
        plot_bgcolor="#050505",
        font=dict(color="#f2f2f2", family="Courier New"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


@st.cache_data(ttl=MARKET_DATA_CACHE_TTL_SECONDS, show_spinner=False)
def build_synthetic_gold_crosses(period, interval):
    required = {
        "Gold/USD Proxy": "GC=F",
        "Silver/USD Proxy": "SI=F",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "USDCHF": "USDCHF=X",
        "AUDUSD": "AUDUSD=X",
    }
    closes = {}
    for label, ticker in required.items():
        df = get_price_data(ticker, period, interval)
        if not df.empty and "Close" in df.columns:
            closes[label] = df["Close"].dropna().rename(label)
    if not closes:
        return pd.DataFrame(), pd.DataFrame()
    source_df = pd.DataFrame(closes).ffill().dropna()
    if source_df.empty or "Gold/USD Proxy" not in source_df.columns:
        return pd.DataFrame(), pd.DataFrame()
    synthetic = pd.DataFrame(index=source_df.index)
    synthetic["XAUUSD Proxy"] = source_df["Gold/USD Proxy"]
    if "EURUSD" in source_df.columns:
        synthetic["XAUEUR Proxy"] = source_df["Gold/USD Proxy"] / source_df["EURUSD"]
    if "GBPUSD" in source_df.columns:
        synthetic["XAUGBP Proxy"] = source_df["Gold/USD Proxy"] / source_df["GBPUSD"]
    if "USDJPY" in source_df.columns:
        synthetic["XAUJPY Proxy"] = source_df["Gold/USD Proxy"] * source_df["USDJPY"]
    if "USDCHF" in source_df.columns:
        synthetic["XAUCHF Proxy"] = source_df["Gold/USD Proxy"] * source_df["USDCHF"]
    if "AUDUSD" in source_df.columns:
        synthetic["XAUAUD Proxy"] = source_df["Gold/USD Proxy"] / source_df["AUDUSD"]
    if "Silver/USD Proxy" in source_df.columns:
        synthetic["XAGUSD Proxy"] = source_df["Silver/USD Proxy"]

    rows = []
    for col in synthetic.columns:
        s = synthetic[col].dropna()
        if len(s) < 2:
            continue
        last = float(s.iloc[-1])
        previous = float(s.iloc[-2])
        change = last - previous
        change_pct = (last / previous - 1) * 100 if previous != 0 else np.nan
        rows.append({"Synthetic Asset": col, "Latest": round(last, 4), "Change": round(change, 4), "Change %": round(change_pct, 2)})
    return pd.DataFrame(rows), synthetic


def build_screener_tables(watchlist_df):
    if watchlist_df is None or watchlist_df.empty:
        return {}
    df = watchlist_df.copy()
    numeric_cols = ["Change %", "Ann. Vol %", "Volume Ratio", "Dist. 20MA %", "Dist. 50MA %", "Dist. 200MA %", "20P Drawdown %"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return {
        "Top Gainers": df.sort_values("Change %", ascending=False).head(15),
        "Top Losers": df.sort_values("Change %", ascending=True).head(15),
        "Highest Volatility": df.sort_values("Ann. Vol %", ascending=False).head(15),
        "Volume Expansion": df.sort_values("Volume Ratio", ascending=False).head(15),
        "Above 20MA": df[df["Dist. 20MA %"] > 0].sort_values("Dist. 20MA %", ascending=False).head(15),
        "Below 20MA": df[df["Dist. 20MA %"] < 0].sort_values("Dist. 20MA %", ascending=True).head(15),
        "Deepest 20P Drawdown": df.sort_values("20P Drawdown %", ascending=True).head(15),
    }


def build_security_snapshot(ticker, period, interval, benchmark_tickers=None):
    ticker = str(ticker or "SPY").upper()
    df = get_price_data(ticker, period, interval)
    if df.empty or "Close" not in df.columns:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), df
    close = df["Close"].dropna()
    last = safe_float(close.iloc[-1]) if len(close) else np.nan
    prev = safe_float(close.iloc[-2]) if len(close) >= 2 else np.nan
    ret1 = (last / prev - 1) * 100 if prev and not np.isnan(prev) else np.nan
    ret5 = (last / safe_float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else np.nan
    ret20 = (last / safe_float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else np.nan
    ret60 = (last / safe_float(close.iloc[-60]) - 1) * 100 if len(close) >= 60 else np.nan
    high20 = safe_float(close.tail(20).max()) if len(close) >= 20 else np.nan
    low20 = safe_float(close.tail(20).min()) if len(close) >= 20 else np.nan
    ma20 = safe_float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else np.nan
    ma50 = safe_float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else np.nan
    ma200 = safe_float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else np.nan
    returns = close.pct_change().dropna()
    realized_vol = returns.std() * np.sqrt(252) * 100 if len(returns) > 2 else np.nan
    snapshot = pd.DataFrame([
        {"Field": "Ticker", "Value": ticker},
        {"Field": "Asset Class", "Value": classify_asset(ticker)},
        {"Field": "Last", "Value": format_number(last, 4)},
        {"Field": "Last Candle %", "Value": format_signed_pct(ret1)},
        {"Field": "5-Period %", "Value": format_signed_pct(ret5)},
        {"Field": "20-Period %", "Value": format_signed_pct(ret20)},
        {"Field": "60-Period %", "Value": format_signed_pct(ret60)},
        {"Field": "Realized Vol %", "Value": format_number(realized_vol)},
        {"Field": "20P High", "Value": format_number(high20, 4)},
        {"Field": "20P Low", "Value": format_number(low20, 4)},
        {"Field": "Dist. 20MA", "Value": format_signed_pct((last / ma20 - 1) * 100 if ma20 and not np.isnan(ma20) else np.nan)},
        {"Field": "Dist. 50MA", "Value": format_signed_pct((last / ma50 - 1) * 100 if ma50 and not np.isnan(ma50) else np.nan)},
        {"Field": "Dist. 200MA", "Value": format_signed_pct((last / ma200 - 1) * 100 if ma200 and not np.isnan(ma200) else np.nan)},
    ])
    technical = pd.DataFrame([
        {"Signal": "Above 20MA", "State": "YES" if last > ma20 else "NO" if not np.isnan(ma20) else "N/A"},
        {"Signal": "Above 50MA", "State": "YES" if last > ma50 else "NO" if not np.isnan(ma50) else "N/A"},
        {"Signal": "Above 200MA", "State": "YES" if last > ma200 else "NO" if not np.isnan(ma200) else "N/A"},
        {"Signal": "Near 20P High", "State": "YES" if high20 and not np.isnan(high20) and last >= high20 * 0.99 else "NO"},
        {"Signal": "Near 20P Low", "State": "YES" if low20 and not np.isnan(low20) and last <= low20 * 1.01 else "NO"},
    ])
    if benchmark_tickers is None:
        benchmark_tickers = ["SPY", "QQQ", "DX-Y.NYB", "^TNX", "^VIX", "GC=F", "BTC-USD"]
    corr_rows = []
    base = close.rename(ticker)
    for bench in benchmark_tickers:
        if bench == ticker:
            continue
        bdf = get_price_data(bench, period, interval)
        if bdf.empty or "Close" not in bdf.columns:
            continue
        joined = pd.concat([base, bdf["Close"].rename(bench)], axis=1).dropna()
        if joined.shape[0] >= 5:
            corr = joined.pct_change().dropna().corr().iloc[0, 1]
            corr_rows.append({"Against": bench, "Return Correlation": round(float(corr), 3)})
    return snapshot, technical, pd.DataFrame(corr_rows), df


def build_relative_value(tickers, period, interval):
    tickers = [str(t).upper() for t in tickers if str(t).strip()]
    if len(tickers) < 2:
        tickers = ["GC=F", "DX-Y.NYB", "^TNX", "^VIX"]
    series = {}
    for ticker in tickers:
        df = get_price_data(ticker, period, interval)
        if not df.empty and "Close" in df.columns:
            series[ticker] = df["Close"].dropna().rename(ticker)
    prices = pd.DataFrame(series).ffill().dropna()
    norm = normalize_to_100(prices)
    returns = prices.pct_change().dropna() if not prices.empty else pd.DataFrame()
    corr = returns.corr() if returns.shape[1] >= 2 else pd.DataFrame()
    spread_df = pd.DataFrame()
    zscore = np.nan
    if prices.shape[1] >= 2:
        a, b = prices.columns[:2]
        ratio = prices[a] / prices[b].replace(0, np.nan)
        z = (ratio - ratio.rolling(20).mean()) / ratio.rolling(20).std()
        spread_df = pd.DataFrame({f"{a}/{b} Ratio": ratio, "20P Z-Score": z}).dropna()
        if not spread_df.empty:
            zscore = safe_float(spread_df["20P Z-Score"].iloc[-1])
    return prices, norm, corr, spread_df, zscore


def tag_news_headline(headline):
    text = str(headline).lower()
    tags = []
    urgency = 1
    gold_bias = "Neutral"
    if any(k in text for k in ["fed", "federal reserve", "powell", "rate", "yields", "treasury"]):
        tags.append("Rates/Fed")
        urgency += 2
    if any(k in text for k in ["inflation", "cpi", "pce", "ppi"]):
        tags.append("Inflation")
        urgency += 2
        gold_bias = "Volatility Risk"
    if any(k in text for k in ["dollar", "dxy", "usd"]):
        tags.append("USD")
        urgency += 1
    if any(k in text for k in ["gold", "bullion", "xau"]):
        tags.append("Gold")
        urgency += 2
    if any(k in text for k in ["war", "attack", "geopolitical", "israel", "iran", "ukraine", "russia", "conflict"]):
        tags.append("Geopolitics")
        urgency += 3
        gold_bias = "Gold Safe-Haven Risk"
    if any(k in text for k in ["oil", "opec", "crude"]):
        tags.append("Oil/Inflation")
        urgency += 1
    if any(k in text for k in ["stocks", "nasdaq", "s&p", "equities", "selloff", "rally"]):
        tags.append("Equities")
    if any(k in text for k in ["bitcoin", "crypto"]):
        tags.append("Crypto")
    if any(k in text for k in ["recession", "jobs", "payrolls", "unemployment", "growth", "gdp", "pmi"]):
        tags.append("Growth/Labor")
        urgency += 1
    if not tags:
        tags = ["General Markets"]
    if "dollar rises" in text or "yields rise" in text or "rates higher" in text:
        gold_bias = "Gold Headwind"
    if "dollar falls" in text or "yields fall" in text or "safe haven" in text:
        gold_bias = "Gold Tailwind"
    urgency_label = "HIGH" if urgency >= 5 else "MEDIUM" if urgency >= 3 else "LOW"
    return ", ".join(tags), gold_bias, urgency_label, urgency


def build_news_intelligence(news_df, keyword=""):
    if news_df is None or news_df.empty:
        return pd.DataFrame()
    df = news_df.copy()
    if keyword:
        mask = df["Headline"].str.contains(keyword, case=False, na=False) | df["Source"].str.contains(keyword, case=False, na=False)
        df = df[mask]
    if df.empty:
        return df
    tagged = df["Headline"].apply(tag_news_headline)
    df["Theme"], df["Gold Read"], df["Urgency"], df["Urgency Score"] = zip(*tagged)
    return df.sort_values(["Urgency Score"], ascending=False)


def build_institutional_alerts(watchlist_df, macro_summary_df, xau_score=None, event_regime=None):
    alerts = []

    def lookup(ticker):
        value = get_row_change(watchlist_df, ticker)
        return value if value is not None else get_row_change(macro_summary_df, ticker)

    spy = lookup("SPY")
    qqq = lookup("QQQ")
    vix = lookup("^VIX")
    dxy = lookup("DX-Y.NYB")
    dollar = lookup("UUP") if lookup("UUP") is not None else dxy
    gold = lookup("GC=F") if lookup("GC=F") is not None else lookup("GLD")
    ten_y = lookup("^TNX")
    thirty_y = lookup("^TYX")
    oil = lookup("CL=F")
    btc = lookup("BTC-USD")
    tlt = lookup("TLT")

    if vix is not None and vix > 3:
        alerts.append(("danger", f"VIX spike {vix:.2f}%: fear impulse is rising."))
    if spy is not None and vix is not None and spy < -1 and vix > 0:
        alerts.append(("danger", "SPY falling while VIX rising: defensive risk-off pressure."))
    if qqq is not None and vix is not None and qqq > 1 and vix < 0:
        alerts.append(("good", "QQQ strong while VIX falls: clean risk-on tape."))
    if dollar is not None and gold is not None and dollar > 0.35 and gold < 0:
        alerts.append(("danger", "Dollar strength + gold weakness: bearish XAU macro squeeze."))
    if dxy is not None and ten_y is not None and gold is not None and dxy > 0 and ten_y > 0 and gold < 0:
        alerts.append(("danger", "DXY up + 10Y up + gold down: classic XAU headwind alignment."))
    if dxy is not None and ten_y is not None and gold is not None and dxy > 0 and ten_y > 0 and gold > 0:
        alerts.append(("warning", "Gold rising despite DXY/yields rising: correlation break, possible safe-haven or flow-driven move."))
    if vix is not None and gold is not None and spy is not None and vix > 0 and gold > 0 and spy < 0:
        alerts.append(("good", "Gold up + VIX up + stocks down: safe-haven impulse detected."))
    if oil is not None and abs(oil) > 2:
        alerts.append(("warning", f"Oil move >2%: inflation/growth repricing risk. Oil change: {oil:.2f}%."))
    if btc is not None and abs(btc) > 3:
        alerts.append(("warning", f"Bitcoin move >3%: speculative liquidity impulse. BTC change: {btc:.2f}%."))
    if tlt is not None and abs(tlt) > 1.2:
        alerts.append(("warning", f"TLT sharp move: bond/rates repricing. TLT change: {tlt:.2f}%."))
    if xau_score is not None:
        if xau_score >= 7:
            alerts.append(("good", f"XAU score {xau_score}/10: strong bullish macro tailwind."))
        elif xau_score <= -7:
            alerts.append(("danger", f"XAU score {xau_score}/10: strong bearish macro headwind."))
        elif -3 <= xau_score <= 3:
            alerts.append(("warning", f"XAU score {xau_score}/10: macro is mixed; avoid forcing direction."))
    if event_regime in ["HIGH EVENT RISK", "EXTREME EVENT RISK"]:
        alerts.append(("danger", f"{event_regime}: reduce conviction around red/orange news windows."))

    if watchlist_df is not None and not watchlist_df.empty and "Volume Ratio" in watchlist_df.columns:
        vol = watchlist_df[pd.to_numeric(watchlist_df["Volume Ratio"], errors="coerce") >= 2]
        for _, row in vol.head(5).iterrows():
            alerts.append(("warning", f"{row['Ticker']} volume spike: {row['Volume Ratio']}x normal."))

    if not alerts:
        alerts.append(("good", "No major institutional alerts detected."))
    return alerts


def calculate_portfolio(portfolio_df, watchlist_df):
    if portfolio_df is None or portfolio_df.empty:
        return pd.DataFrame()
    results = []
    for _, row in portfolio_df.iterrows():
        ticker = str(row.get("Ticker", "")).upper().strip()
        if not ticker:
            continue
        side = str(row.get("Side", "Long"))
        quantity = safe_float(row.get("Quantity", 0))
        entry = safe_float(row.get("Entry Price", 0))
        stop = safe_float(row.get("Stop Loss", np.nan))
        target = safe_float(row.get("Target", np.nan))
        if np.isnan(quantity) or np.isnan(entry) or entry == 0:
            continue
        current = np.nan
        if watchlist_df is not None and not watchlist_df.empty:
            match = watchlist_df[watchlist_df["Ticker"] == ticker]
            if not match.empty:
                current = safe_float(match.iloc[0]["Last"])
        if np.isnan(current):
            df = get_price_data(ticker, "5d", "1d")
            if not df.empty and "Close" in df.columns:
                current = safe_float(df["Close"].dropna().iloc[-1])
        if np.isnan(current):
            continue
        is_short = side.lower() == "short"
        pnl = (entry - current) * quantity if is_short else (current - entry) * quantity
        pnl_pct = (entry / current - 1) * 100 if is_short and current else (current / entry - 1) * 100 if entry else np.nan
        market_value = abs(quantity * current)
        risk_to_stop = np.nan
        reward_to_target = np.nan
        rr = np.nan
        if not np.isnan(stop):
            risk_to_stop = (stop - current) * quantity if is_short else (current - stop) * quantity
            risk_to_stop = abs(risk_to_stop)
        if not np.isnan(target):
            reward_to_target = (current - target) * quantity if is_short else (target - current) * quantity
            reward_to_target = max(reward_to_target, 0)
        if not np.isnan(risk_to_stop) and risk_to_stop != 0 and not np.isnan(reward_to_target):
            rr = reward_to_target / risk_to_stop
        results.append({
            "Ticker": ticker,
            "Asset Class": classify_asset(ticker),
            "Side": side,
            "Quantity": quantity,
            "Entry Price": round(entry, 4),
            "Current Price": round(current, 4),
            "Market Value": round(market_value, 2),
            "PnL": round(pnl, 2),
            "PnL %": round(pnl_pct, 2) if not np.isnan(pnl_pct) else None,
            "Stop Loss": round(stop, 4) if not np.isnan(stop) else None,
            "Target": round(target, 4) if not np.isnan(target) else None,
            "Risk To Stop": round(risk_to_stop, 2) if not np.isnan(risk_to_stop) else None,
            "Reward To Target": round(reward_to_target, 2) if not np.isnan(reward_to_target) else None,
            "Live R:R": round(rr, 2) if not np.isnan(rr) else None,
        })
    return pd.DataFrame(results)


def build_portfolio_risk_tables(portfolio_result):
    if portfolio_result is None or portfolio_result.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    by_class = portfolio_result.groupby("Asset Class", as_index=False).agg({"Market Value": "sum", "PnL": "sum", "Risk To Stop": "sum"})
    total_mv = by_class["Market Value"].sum()
    by_class["Exposure %"] = by_class["Market Value"] / total_mv * 100 if total_mv else np.nan
    concentration = portfolio_result.sort_values("Market Value", ascending=False).head(10)
    shock_rows = []
    for shock_pct in [-3, -2, -1, 1, 2, 3]:
        shock_pnl = 0
        for _, row in portfolio_result.iterrows():
            direction = -1 if str(row["Side"]).lower() == "short" else 1
            shock_pnl += row["Market Value"] * (shock_pct / 100) * direction
        shock_rows.append({"Uniform Price Shock": f"{shock_pct:+.0f}%", "Estimated PnL Impact": round(shock_pnl, 2)})
    return by_class, concentration, pd.DataFrame(shock_rows)

# ============================================================
# SIDEBAR AND DATA LOAD
# ============================================================

st.sidebar.markdown("## MARGIN MANOR V75")
st.sidebar.caption("Bloomberg-style command center using free/delayed data.")

watchlist_input = st.sidebar.text_area("Watchlist tickers", value=DEFAULT_WATCHLIST, height=150)
tickers = [ticker.strip().upper() for ticker in watchlist_input.split(",") if ticker.strip()]

period = st.sidebar.selectbox("Market data period", ["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
interval = st.sidebar.selectbox("Market data interval", ["1d", "1h", "30m", "15m", "5m"], index=0)
chart_group = st.sidebar.selectbox("Chart asset group", list(CHART_UNIVERSE.keys()))
selected_chart_ticker = st.sidebar.selectbox("Main chart ticker", CHART_UNIVERSE[chart_group], index=0)

st.sidebar.markdown("---")
manual_screen = st.sidebar.selectbox("Manual function screen", FUNCTION_SCREENS, index=0)
sidebar_news_filter = st.sidebar.text_input("News filter", value="")
st.sidebar.markdown("---")
st.sidebar.markdown("### Auto-refresh")
auto_refresh_enabled = st.sidebar.checkbox("Auto-refresh terminal", value=True)
auto_refresh_seconds = st.sidebar.number_input(
    "Page refresh interval, seconds",
    min_value=10,
    max_value=300,
    value=DEFAULT_AUTO_REFRESH_SECONDS,
    step=5,
    help="This reruns the Streamlit app automatically. Market/news data still obeys cache TTL so free APIs are not spammed.",
)
show_live_seconds_clock = st.sidebar.checkbox("Show live seconds clock", value=True)

if auto_refresh_enabled:
    refresh_ms = int(auto_refresh_seconds) * 1000
    if st_autorefresh is not None:
        st_autorefresh(interval=refresh_ms, limit=None, key="margin_manor_v75_auto_refresh")
    else:
        # Fallback if streamlit-autorefresh is not installed.
        # This still removes the need to refresh manually, but installing streamlit-autorefresh is smoother.
        components.html(
            f"""
            <script>
            setTimeout(function() {{
                window.parent.location.reload();
            }}, {refresh_ms});
            </script>
            """,
            height=0,
        )
        st.sidebar.warning("For smoother auto-refresh, install: streamlit-autorefresh")

st.sidebar.markdown("---")
st.sidebar.caption(f"Auto-refresh: {'ON' if auto_refresh_enabled else 'OFF'} every {int(auto_refresh_seconds)}s")
st.sidebar.caption(f"Market cache TTL: {MARKET_DATA_CACHE_TTL_SECONDS}s | News TTL: {NEWS_CACHE_TTL_SECONDS}s")
st.sidebar.caption("Data mode: FREE / DELAYED / RESEARCH")
st.sidebar.caption("Not an execution platform. Not investment advice.")

with st.spinner("Loading terminal data..."):
    watchlist_df, prices_df = build_watchlist(tickers, period, interval)
    macro_summary_df, macro_price_df = get_macro_proxy_data(MACRO_TICKERS, period, interval)

# ============================================================
# HEADER / COMMAND ROUTER
# ============================================================

st.markdown("# MARGIN MANOR TERMINAL V75")
st.markdown('<div class="terminal-subtitle">Function-code workflow | Cross-asset monitor | XAU cockpit | Relative value | News intelligence | Portfolio risk</div>', unsafe_allow_html=True)

if not watchlist_df.empty:
    st.markdown(build_ticker_tape(watchlist_df), unsafe_allow_html=True)

cbar1, cbar2 = st.columns([3.5, 1])
with cbar1:
    command = st.text_input(
        "Command",
        placeholder="Examples: XAU <GO> | DES GC=F <GO> | GP AAPL <GO> | RV GC=F DX-Y.NYB ^TNX <GO> | CN FED <GO> | ECO <GO> | HELP <GO>",
        label_visibility="collapsed",
    )
with cbar2:
    if show_live_seconds_clock:
        components.html(live_sgt_clock_html("SGT LIVE"), height=46)
    else:
        st.markdown(
            f"""
            <div class="function-bar">SGT {datetime.now(ZoneInfo('Asia/Singapore')).strftime('%d %b %Y %H:%M:%S')}</div>
            """,
            unsafe_allow_html=True,
        )

command_info = parse_command(command)
active_screen = command_info["screen"] if command.strip() else manual_screen
active_ticker = command_info["ticker"] or selected_chart_ticker
active_tickers = command_info["tickers"] if command_info["tickers"] else [active_ticker]
news_filter = command_info["keyword"] if command_info["keyword"] else sidebar_news_filter

st.markdown(
    f"""
    <div class="function-bar">
        ACTIVE: {html.escape(active_screen)} | RESPONSE: {html.escape(command_info['message'])}
    </div>
    """,
    unsafe_allow_html=True,
)

# Core scores used by multiple pages
regime, regime_class, risk_score, risk_signals = compute_risk_regime(watchlist_df, macro_summary_df)
xau_score, xau_bias, xau_action, xau_driver_df = compute_xau_command_score(watchlist_df, macro_summary_df)

# Optional calendar load only for ECO/XAU/ALRT/PORT home context
ff_display_df = pd.DataFrame()
event_score, event_regime, active_events = 0, "NO CALENDAR DATA", pd.DataFrame()
if active_screen in [FUNCTION_SCREENS[0], FUNCTION_SCREENS[4], FUNCTION_SCREENS[8], FUNCTION_SCREENS[9]]:
    ff_raw_df = fetch_forexfactory_calendar()
    ff_display_df = build_forexfactory_display(
        ff_raw_df,
        currencies=["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY"],
        impacts=["Red", "Orange"],
        source_timezone="America/New_York",
    )
    event_score, event_regime, active_events = build_event_risk_score(ff_display_df)

institutional_alerts = build_institutional_alerts(watchlist_df, macro_summary_df, xau_score=xau_score, event_regime=event_regime)

# ============================================================
# PAGE RENDERERS
# ============================================================

def page_home():
    st.markdown("## MMKT <GO> MARKET COMMAND CENTER")
    if watchlist_df.empty:
        st.warning("No market data loaded. Check tickers, interval, or connection.")
        return

    top_gainer = watchlist_df.sort_values("Change %", ascending=False).iloc[0]
    top_loser = watchlist_df.sort_values("Change %", ascending=True).iloc[0]
    highest_vol = watchlist_df.sort_values("Ann. Vol %", ascending=False).iloc[0]
    avg_move = pd.to_numeric(watchlist_df["Change %"], errors="coerce").mean()
    score_class = "positive" if xau_score > 0 else "negative" if xau_score < 0 else "neutral"

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1: terminal_box("Top Gainer", top_gainer["Ticker"], format_signed_pct(top_gainer["Change %"]), "positive")
    with m2: terminal_box("Top Loser", top_loser["Ticker"], format_signed_pct(top_loser["Change %"]), "negative")
    with m3: terminal_box("High Vol", highest_vol["Ticker"], f"{highest_vol['Ann. Vol %']}% Ann. Vol", "neutral")
    with m4: terminal_box("Risk Regime", regime, f"Score {risk_score} | Avg {format_signed_pct(avg_move)}", regime_class)
    with m5: terminal_box("XAU Score", f"{xau_score}/10", xau_bias, score_class)
    with m6: terminal_box("Event Risk", event_regime, f"Score {event_score} | {get_next_high_impact_event(ff_display_df)}", "negative" if event_regime in ["HIGH EVENT RISK", "EXTREME EVENT RISK"] else "neutral")

    left, mid, right = st.columns([1.15, 1.7, 1.05])
    with left:
        st.markdown('<div class="terminal-panel"><div class="terminal-panel-title">RISK ENGINE SIGNALS</div>', unsafe_allow_html=True)
        for signal in risk_signals[:8]:
            st.markdown(f'<div class="terminal-small">• {html.escape(signal)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### MARKET WATCHLIST")
        display_cols = ["Ticker", "Last", "Change %", "5-Period %", "20-Period %", "Ann. Vol %", "Trend"]
        st.dataframe(watchlist_df[display_cols].style.map(color_value, subset=["Change %", "5-Period %", "20-Period %"]), use_container_width=True, height=445)

    with mid:
        chart_df = get_price_data(active_ticker, period, interval)
        if chart_df.empty:
            st.warning(f"No chart data available for {active_ticker}.")
        else:
            st.plotly_chart(create_candlestick_chart(chart_df, active_ticker, height=515), use_container_width=True)
        st.markdown("### MACRO STRIP")
        if not macro_summary_df.empty:
            macro_cols = ["Macro Driver", "Ticker", "Latest", "Change", "Change %", "5-Period %"]
            st.dataframe(macro_summary_df[macro_cols].style.map(color_value, subset=["Change", "Change %", "5-Period %"]), use_container_width=True, height=260)

    with right:
        st.markdown("### ALERT DECK")
        for kind, txt in institutional_alerts[:9]:
            alert_card(txt, kind)
        st.markdown("### TOP NEWS INTEL")
        news_df = build_news_intelligence(fetch_rss_news(), news_filter).head(8)
        if news_df.empty:
            st.caption("No news loaded or no matching news filter.")
        else:
            for _, row in news_df.iterrows():
                st.markdown(
                    f"""
                    <div class="news-card">
                        <div class="news-source">{html.escape(str(row['Source']))} | {html.escape(str(row.get('Urgency','')))} | {html.escape(str(row.get('Theme','')))}</div>
                        <div class="news-title">{html.escape(str(row['Headline']))}</div>
                        <div class="terminal-small">Gold read: {html.escape(str(row.get('Gold Read','Neutral')))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def page_chart():
    st.markdown(f"## GP <GO> PRICE GRAPH: {active_ticker}")
    df = get_price_data(active_ticker, period, interval)
    if df.empty:
        st.warning(f"No chart data available for {active_ticker}.")
        return
    st.plotly_chart(create_candlestick_chart(df, active_ticker, height=650), use_container_width=True)
    close = df["Close"].dropna()
    cols = st.columns(6)
    values = [
        ("Last", format_number(close.iloc[-1], 4), "neutral"),
        ("1P", format_signed_pct((close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else np.nan), pct_class((close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else np.nan)),
        ("5P", format_signed_pct((close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else np.nan), pct_class((close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else np.nan)),
        ("20P", format_signed_pct((close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else np.nan), pct_class((close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else np.nan)),
        ("20P High", format_number(close.tail(20).max(), 4) if len(close) >= 20 else "N/A", "neutral"),
        ("20P Low", format_number(close.tail(20).min(), 4) if len(close) >= 20 else "N/A", "neutral"),
    ]
    for col, (title, value, css) in zip(cols, values):
        with col:
            terminal_box(title, value, "", css)


def page_security():
    st.markdown(f"## DES <GO> SECURITY DESCRIPTION: {active_ticker}")
    snapshot, technical, corr, df = build_security_snapshot(active_ticker, period, interval)
    if df.empty:
        st.warning(f"No security data available for {active_ticker}.")
        return
    left, mid, right = st.columns([1, 1.6, 1])
    with left:
        st.markdown("### SECURITY MASTER")
        st.dataframe(snapshot, use_container_width=True, height=430)
        st.markdown("### TECHNICAL STATE")
        st.dataframe(technical, use_container_width=True, height=220)
    with mid:
        st.plotly_chart(create_candlestick_chart(df, active_ticker, height=610), use_container_width=True)
    with right:
        st.markdown("### CROSS-ASSET CORRELATION")
        if corr.empty:
            st.caption("Not enough data for correlation.")
        else:
            st.dataframe(corr.style.map(color_value, subset=["Return Correlation"]), use_container_width=True, height=270)
        st.markdown("### RELATED NEWS")
        news_key = active_ticker.replace("=X", "").replace("=F", "").replace("^", "")
        news_df = build_news_intelligence(fetch_rss_news(), news_key).head(8)
        if news_df.empty:
            news_df = build_news_intelligence(fetch_rss_news(), "").head(5)
        for _, row in news_df.iterrows():
            st.markdown(
                f"""
                <div class="news-card">
                    <div class="news-source">{html.escape(str(row['Source']))} | {html.escape(str(row.get('Theme','')))}</div>
                    <div class="news-title">{html.escape(str(row['Headline']))}</div>
                    <a href="{html.escape(str(row['Link']))}" target="_blank">Open story</a>
                </div>
                """,
                unsafe_allow_html=True,
            )


def page_relative_value():
    st.markdown("## RV <GO> RELATIVE VALUE")
    tick_input_default = " ".join(active_tickers) if len(active_tickers) >= 2 else "GC=F DX-Y.NYB ^TNX ^VIX"
    tick_input = st.text_input("RV ticker set", value=tick_input_default, help="Example: GC=F DX-Y.NYB ^TNX ^VIX")
    rv_tickers = [x.upper() for x in tick_input.replace(",", " ").split() if x.strip()]
    prices, norm, corr, spread_df, zscore = build_relative_value(rv_tickers, period, interval)
    if prices.empty or norm.empty:
        st.warning("Not enough valid data for relative value.")
        return
    rv1, rv2, rv3 = st.columns(3)
    with rv1: terminal_box("RV Set", ", ".join(prices.columns[:4]), "Normalized to 100", "neutral")
    with rv2: terminal_box("Pair Z-Score", format_number(zscore), "First ticker / second ticker 20P z-score", "positive" if zscore > 1 else "negative" if zscore < -1 else "neutral")
    with rv3: terminal_box("Signal", "Rich" if zscore > 1.5 else "Cheap" if zscore < -1.5 else "Neutral", "Based on pair ratio z-score", "negative" if abs(zscore) > 1.5 else "neutral")
    fig = px.line(norm, x=norm.index, y=norm.columns, title="RV Normalized Performance: 100 = first visible point")
    fig.update_layout(template="plotly_dark", height=520, paper_bgcolor="#000000", plot_bgcolor="#050505", font=dict(color="#f2f2f2", family="Courier New"), margin=dict(l=15, r=15, t=45, b=15))
    st.plotly_chart(fig, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### RETURN CORRELATION")
        if corr.empty:
            st.caption("Correlation unavailable.")
        else:
            fig_corr = px.imshow(corr, text_auto=True, aspect="auto", title="RV Return Correlation")
            fig_corr.update_layout(template="plotly_dark", height=430, paper_bgcolor="#000000", plot_bgcolor="#050505", font=dict(color="#f2f2f2"))
            st.plotly_chart(fig_corr, use_container_width=True)
    with c2:
        st.markdown("### PAIR SPREAD / Z-SCORE")
        if spread_df.empty:
            st.caption("Need at least two valid tickers.")
        else:
            fig_spread = px.line(spread_df, x=spread_df.index, y=spread_df.columns, title="Pair Ratio and 20P Z-Score")
            fig_spread.update_layout(template="plotly_dark", height=430, paper_bgcolor="#000000", plot_bgcolor="#050505", font=dict(color="#f2f2f2"))
            st.plotly_chart(fig_spread, use_container_width=True)


def page_xau():
    st.markdown("## XAU <GO> GOLD / XAUUSD INSTITUTIONAL COCKPIT")
    score_class = "positive" if xau_score > 0 else "negative" if xau_score < 0 else "neutral"
    top_driver = "N/A"
    if not xau_driver_df.empty:
        ranked = xau_driver_df.copy()
        ranked["Abs Contribution"] = ranked["Contribution"].abs()
        if not ranked.empty:
            r = ranked.sort_values("Abs Contribution", ascending=False).iloc[0]
            top_driver = f"{r['Driver']} / {r['Effect on XAU']}"
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: terminal_box("XAU Score", f"{xau_score}/10", "Positive = tailwind | Negative = headwind", score_class)
    with k2: terminal_box("XAU Bias", xau_bias, "Macro-based, not entry signal", score_class)
    with k3: terminal_box("Top Driver", top_driver, "Largest weighted contribution", "neutral")
    with k4: terminal_box("Event Risk", event_regime, f"Score {event_score}", "negative" if event_regime in ["HIGH EVENT RISK", "EXTREME EVENT RISK"] else "neutral")
    with k5: terminal_box("Action", "WAIT CONFIRM" if abs(xau_score) >= 4 else "WAIT", xau_action, score_class)

    left, center, right = st.columns([1.25, 1.55, 1])
    with left:
        st.markdown("### XAU DRIVER MATRIX")
        if xau_driver_df.empty:
            st.warning("XAU driver data unavailable.")
        else:
            st.dataframe(xau_driver_df.style.map(color_value, subset=["Change %", "Contribution"]), use_container_width=True, height=515)
    with center:
        st.markdown("### GOLD CHART")
        gold_df = get_price_data("GC=F", period, interval)
        if gold_df.empty:
            st.warning("Gold futures data unavailable.")
        else:
            st.plotly_chart(create_candlestick_chart(gold_df, "GC=F", height=500), use_container_width=True)
        st.markdown("### GOLD CROSS MAP")
        cross_summary, cross_prices = build_synthetic_gold_crosses(period, interval)
        if cross_summary.empty:
            st.warning("Synthetic cross data unavailable.")
        else:
            st.dataframe(cross_summary.style.map(color_value, subset=["Change", "Change %"]), use_container_width=True, height=230)
    with right:
        st.markdown("### XAU ALERTS")
        for kind, txt in institutional_alerts[:8]:
            alert_card(txt, kind)
        st.markdown("### TRADE CHECKLIST")
        checklist = pd.DataFrame([
            {"Condition": "Macro score aligned", "State": "YES" if abs(xau_score) >= 4 else "NO"},
            {"Condition": "Red/orange event risk controlled", "State": "NO" if event_regime in ["HIGH EVENT RISK", "EXTREME EVENT RISK"] else "YES"},
            {"Condition": "Wait for price confirmation", "State": "ALWAYS"},
            {"Condition": "DXY/yield agreement checked", "State": "YES"},
            {"Condition": "XAU crosses confirmation", "State": "CHECK XAUEUR/XAUGBP/XAG"},
            {"Condition": "Invalidation level defined", "State": "MANUAL"},
        ])
        st.dataframe(checklist, use_container_width=True, height=250)


def page_rates():
    st.markdown("## RATES <GO> YIELD CURVE")
    required_curve = ["3M Yield Proxy", "5Y Yield Proxy", "10Y Yield Proxy", "30Y Yield Proxy"]
    curve_rows = []
    for label in required_curve:
        match = macro_summary_df[macro_summary_df["Macro Driver"] == label] if not macro_summary_df.empty else pd.DataFrame()
        if not match.empty:
            curve_rows.append({"Maturity": label.replace(" Yield Proxy", ""), "Yield %": safe_float(match.iloc[0]["Latest"]), "Change": safe_float(match.iloc[0]["Change"])})
    curve_df = pd.DataFrame(curve_rows)
    if curve_df.empty:
        st.warning("Yield data unavailable.")
        return
    c1, c2 = st.columns([1.55, 1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve_df["Maturity"], y=curve_df["Yield %"], mode="lines+markers", name="Yield Curve"))
        fig.update_layout(template="plotly_dark", height=510, title="US Yield Curve Proxy", yaxis_title="Yield %", paper_bgcolor="#000000", plot_bgcolor="#050505", font=dict(color="#f2f2f2"))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("### CURVE TABLE")
        st.dataframe(curve_df.style.map(color_value, subset=["Change"]), use_container_width=True, height=220)
        cv = dict(zip(curve_df["Maturity"], curve_df["Yield %"]))
        spreads = []
        for name, a, b in [("10Y - 3M", "10Y", "3M"), ("10Y - 5Y", "10Y", "5Y"), ("30Y - 10Y", "30Y", "10Y")]:
            if a in cv and b in cv:
                spreads.append({"Spread": name, "Value": round(cv[a] - cv[b], 4)})
        st.markdown("### CURVE SPREADS")
        st.dataframe(pd.DataFrame(spreads).style.map(color_value, subset=["Value"]), use_container_width=True, height=170)
        st.markdown("### RATES READ")
        st.dataframe(pd.DataFrame([
            {"Condition": "Bear steepening", "Meaning": "Long yields rise; inflation/fiscal concern."},
            {"Condition": "Bull steepening", "Meaning": "Front-end falls; easing/growth slowdown."},
            {"Condition": "Flattening", "Meaning": "Policy tightening or long-end growth concern."},
            {"Condition": "Inversion", "Meaning": "Short yields above long yields; tightening/recession risk."},
        ]), use_container_width=True, height=230)


def page_macro():
    st.markdown("## MACRO <GO> MACRO DASHBOARD")
    if macro_summary_df.empty:
        st.warning("Macro proxy data unavailable.")
        return
    st.caption("Free-data proxy dashboard. For institutional-grade macro, connect paid/official feeds later.")
    st.dataframe(macro_summary_df.style.map(color_value, subset=["Change", "Change %", "5-Period %", "20-Period %"]), use_container_width=True, height=360)
    macro_choice = st.selectbox("Macro driver chart", macro_summary_df["Macro Driver"].tolist())
    if not macro_price_df.empty and macro_choice in macro_price_df.columns:
        fig = px.line(macro_price_df[[macro_choice]].dropna(), x=macro_price_df[[macro_choice]].dropna().index, y=macro_choice, title=f"{macro_choice} Proxy")
        fig.update_layout(template="plotly_dark", height=500, paper_bgcolor="#000000", plot_bgcolor="#050505", font=dict(color="#f2f2f2"))
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("### INSTITUTIONAL MACRO MAP")
    guide = pd.DataFrame([
        {"Driver": "Yields", "Institutional Read": "Discount rate and opportunity cost. Higher yields usually pressure gold and duration assets."},
        {"Driver": "USD/DXY", "Institutional Read": "Global funding pressure. Strong USD often pressures commodities and EM risk."},
        {"Driver": "VIX", "Institutional Read": "Fear/hedging demand. Rising VIX can support safe-haven gold but hurt risk assets."},
        {"Driver": "Oil/Copper", "Institutional Read": "Inflation and growth impulse. Oil = inflation shock; copper = global growth sensitivity."},
        {"Driver": "SPX/NDX/BTC", "Institutional Read": "Risk appetite and liquidity proxies."},
    ])
    st.dataframe(guide, use_container_width=True, height=245)


def page_news():
    st.markdown("## CN <GO> NEWS INTELLIGENCE")
    refresh = st.button("Refresh RSS News")
    if refresh:
        fetch_rss_news.clear()
    news_df = build_news_intelligence(fetch_rss_news(), news_filter)
    if news_df.empty:
        st.warning("No news loaded or no matching filter.")
        return
    n1, n2, n3 = st.columns(3)
    with n1: terminal_box("News Items", len(news_df), f"Filter: {news_filter or 'ALL'}", "neutral")
    with n2: terminal_box("High Urgency", len(news_df[news_df["Urgency"] == "HIGH"]), "Tagged by keyword logic", "negative" if len(news_df[news_df["Urgency"] == "HIGH"]) else "neutral")
    with n3: terminal_box("Gold-Relevant", len(news_df[news_df["Theme"].str.contains("Gold|Fed|Rates|Inflation|USD|Geopolitics", na=False)]), "XAU-sensitive themes", "neutral")
    st.dataframe(news_df[["Source", "Published", "Urgency", "Theme", "Gold Read", "Headline"]].head(60), use_container_width=True, height=520)
    st.markdown("### NEWS CARDS")
    for _, row in news_df.head(20).iterrows():
        st.markdown(
            f"""
            <div class="news-card">
                <div class="news-source">{html.escape(str(row['Source']))} | {html.escape(str(row['Urgency']))} | {html.escape(str(row['Theme']))}</div>
                <div class="news-title">{html.escape(str(row['Headline']))}</div>
                <div class="terminal-small">Gold read: {html.escape(str(row['Gold Read']))}</div>
                <a href="{html.escape(str(row['Link']))}" target="_blank">Open story</a>
            </div>
            """,
            unsafe_allow_html=True,
        )


def page_econ():
    st.markdown("## ECO <GO> ECONOMIC CALENDAR")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        currencies = st.multiselect("Currencies", ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY"], default=["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY"])
    with f2:
        impacts = st.multiselect("Impact", ["Red", "Orange", "Yellow", "Low"], default=["Red", "Orange"])
    with f3:
        source_timezone = st.selectbox("Source timezone", ["America/New_York", "Asia/Singapore", "UTC"], index=0)
    with f4:
        if st.button("Refresh Calendar"):
            fetch_forexfactory_calendar.clear()
    raw = fetch_forexfactory_calendar()
    display = build_forexfactory_display(raw, currencies=currencies, impacts=impacts, source_timezone=source_timezone)
    score, reg, active = build_event_risk_score(display)
    k1, k2, k3 = st.columns(3)
    with k1: terminal_box("Event Risk", reg, "Upcoming filtered events", "negative" if reg in ["HIGH EVENT RISK", "EXTREME EVENT RISK"] else "neutral")
    with k2: terminal_box("Event Score", score, "Red 3 | Orange 2 | Yellow 1", "neutral")
    with k3: terminal_box("Next Event", get_next_high_impact_event(display), "Singapore time", "neutral")
    if display.empty:
        st.warning("Calendar could not be loaded or no events match your filters.")
        return
    cols = ["SG Date", "SG Time", "Countdown", "Currency", "Impact", "Event", "Actual", "Forecast", "Previous"]
    st.dataframe(display[cols].style.map(color_impact, subset=["Impact"]), use_container_width=True, height=540)
    csv_data = display.drop(columns=["SG Datetime"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("Download Calendar CSV", data=csv_data, file_name="margin_manor_economic_calendar.csv", mime="text/csv")


def page_alerts():
    st.markdown("## ALRT <GO> INSTITUTIONAL ALERT DECK")
    for kind, txt in institutional_alerts:
        alert_card(txt, kind)
    st.markdown("### ALERT LOGIC")
    logic = pd.DataFrame([
        {"Alert": "DXY up + 10Y up + gold down", "Meaning": "Classic bearish macro pressure for XAU."},
        {"Alert": "Gold up despite DXY/yields up", "Meaning": "Correlation break; possible safe-haven or positioning flow."},
        {"Alert": "Gold up + VIX up + stocks down", "Meaning": "Safe-haven impulse."},
        {"Alert": "High event risk", "Meaning": "Red/orange calendar density is high; beware fake moves."},
        {"Alert": "Volume spike", "Meaning": "Participation above normal; move may be institutional or news-driven."},
    ])
    st.dataframe(logic, use_container_width=True, height=260)


def page_portfolio():
    st.markdown("## PORT <GO> PORTFOLIO / RISK MONITOR")
    st.caption("Manual portfolio tracker. This does not send orders.")
    if "portfolio_input_v75" not in st.session_state:
        st.session_state["portfolio_input_v75"] = pd.DataFrame([
            {"Ticker": "GC=F", "Side": "Long", "Quantity": 1, "Entry Price": 2300.00, "Stop Loss": 2270.00, "Target": 2420.00},
            {"Ticker": "TLT", "Side": "Long", "Quantity": 1, "Entry Price": 90.00, "Stop Loss": 87.50, "Target": 100.00},
            {"Ticker": "QQQ", "Side": "Long", "Quantity": 1, "Entry Price": 450.00, "Stop Loss": 435.00, "Target": 500.00},
        ])
    edited = st.data_editor(
        st.session_state["portfolio_input_v75"],
        num_rows="dynamic",
        use_container_width=True,
        column_config={"Side": st.column_config.SelectboxColumn("Side", options=["Long", "Short"], required=True)},
    )
    st.session_state["portfolio_input_v75"] = edited
    result = calculate_portfolio(edited, watchlist_df)
    if result.empty:
        st.warning("No valid portfolio rows to calculate.")
        return
    total_value = pd.to_numeric(result["Market Value"], errors="coerce").sum()
    total_pnl = pd.to_numeric(result["PnL"], errors="coerce").sum()
    total_risk = pd.to_numeric(result["Risk To Stop"], errors="coerce").sum()
    p1, p2, p3, p4 = st.columns(4)
    with p1: terminal_box("Total Market Value", f"${total_value:,.2f}", "Gross absolute exposure", "neutral")
    with p2: terminal_box("Total PnL", f"${total_pnl:,.2f}", format_signed_pct(total_pnl / total_value * 100 if total_value else np.nan), "positive" if total_pnl > 0 else "negative" if total_pnl < 0 else "neutral")
    with p3: terminal_box("Risk To Stop", f"${total_risk:,.2f}", "Based on manual stop inputs", "negative" if total_risk > 0 else "neutral")
    with p4: terminal_box("Concentration", result.sort_values("Market Value", ascending=False).iloc[0]["Ticker"], "Largest position", "neutral")
    st.dataframe(result.style.map(color_value, subset=["PnL", "PnL %", "Risk To Stop", "Reward To Target", "Live R:R"]), use_container_width=True, height=330)
    by_class, concentration, shocks = build_portfolio_risk_tables(result)
    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown("### EXPOSURE BY ASSET CLASS")
        st.dataframe(by_class.style.map(color_value, subset=["PnL"]), use_container_width=True, height=270)
    with r2:
        st.markdown("### POSITION CONCENTRATION")
        st.dataframe(concentration[["Ticker", "Asset Class", "Market Value", "PnL", "Risk To Stop"]].style.map(color_value, subset=["PnL", "Risk To Stop"]), use_container_width=True, height=270)
    with r3:
        st.markdown("### SCENARIO SHOCK")
        st.dataframe(shocks.style.map(color_value, subset=["Estimated PnL Impact"]), use_container_width=True, height=270)
    st.markdown("### TRADE JOURNAL")
    if "trade_journal_v75" not in st.session_state:
        st.session_state["trade_journal_v75"] = pd.DataFrame([
            {"Date": datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d"), "Ticker": "GC=F", "Bias": xau_bias, "Setup": "Macro + price confirmation", "Entry Reason": "", "Exit Reason": "", "Result": "Open"}
        ])
    journal = st.data_editor(st.session_state["trade_journal_v75"], num_rows="dynamic", use_container_width=True)
    st.session_state["trade_journal_v75"] = journal


def page_screener():
    st.markdown("## EQSC <GO> MARKET SCREENER")
    if watchlist_df.empty:
        st.warning("No watchlist data available.")
        return
    tables = build_screener_tables(watchlist_df)
    choice = st.selectbox("Screener", list(tables.keys()))
    selected = tables[choice]
    cols = ["Ticker", "Asset Class", "Last", "Change %", "5-Period %", "20-Period %", "Ann. Vol %", "Volume Ratio", "Dist. 20MA %", "Dist. 50MA %", "Dist. 200MA %", "Trend"]
    st.dataframe(selected[[c for c in cols if c in selected.columns]].style.map(color_value, subset=[c for c in ["Change %", "5-Period %", "20-Period %", "Dist. 20MA %", "Dist. 50MA %", "Dist. 200MA %"] if c in selected.columns]), use_container_width=True, height=560)


def page_corr():
    st.markdown("## CORR <GO> CORRELATION MATRIX")
    default = " ".join(active_tickers) if len(active_tickers) >= 2 else "GC=F DX-Y.NYB ^TNX ^VIX SPY QQQ BTC-USD"
    corr_input = st.text_input("Correlation ticker set", value=default)
    corr_tickers = [x.upper() for x in corr_input.replace(",", " ").split() if x.strip()]
    series = {}
    for ticker in corr_tickers:
        df = get_price_data(ticker, period, interval)
        if not df.empty and "Close" in df.columns:
            series[ticker] = df["Close"].dropna().rename(ticker)
    prices = pd.DataFrame(series).dropna()
    if prices.empty or prices.shape[1] < 2:
        st.warning("Not enough valid data for correlation matrix.")
        return
    corr = prices.pct_change().dropna().corr()
    fig = px.imshow(corr, text_auto=True, aspect="auto", title="Return Correlation Matrix")
    fig.update_layout(template="plotly_dark", height=650, paper_bgcolor="#000000", plot_bgcolor="#050505", font=dict(color="#f2f2f2"))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Correlation ranges from -1 to +1. Positive = move together. Negative = move opposite.")


def page_asset_map():
    st.markdown("## MAP <GO> CROSS-ASSET MAP")
    if watchlist_df.empty:
        st.warning("Watchlist data unavailable.")
        return
    group_cols = st.columns(3)
    for idx, (group_name, group_tickers) in enumerate(ASSET_GROUPS.items()):
        with group_cols[idx % 3]:
            st.markdown(f'<div class="terminal-panel"><div class="terminal-panel-title">{html.escape(group_name)}</div>', unsafe_allow_html=True)
            group_data = watchlist_df[watchlist_df["Ticker"].isin(group_tickers)].copy()
            if group_data.empty:
                st.markdown('<div class="terminal-small">No matching tickers loaded.</div>', unsafe_allow_html=True)
            else:
                mini = group_data[["Ticker", "Last", "Change %", "5-Period %", "Trend"]]
                st.dataframe(mini.style.map(color_value, subset=["Change %", "5-Period %"]), use_container_width=True, height=210)
            st.markdown("</div>", unsafe_allow_html=True)


def page_help():
    st.markdown("## HELP <GO> FUNCTION DIRECTORY")
    st.markdown('<div class="command-help">Use Bloomberg-style commands in the command bar. The app routes to one active function screen instead of behaving only like a website tab.</div>', unsafe_allow_html=True)
    help_df = pd.DataFrame([
        {"Command": "MMKT <GO>", "Screen": "Market Command Center", "Example": "MMKT <GO>"},
        {"Command": "GP <TICKER> <GO>", "Screen": "Price Graph", "Example": "GP GC=F <GO>"},
        {"Command": "DES <TICKER> <GO>", "Screen": "Security Description", "Example": "DES AAPL <GO>"},
        {"Command": "RV <A> <B> <C> <GO>", "Screen": "Relative Value", "Example": "RV GC=F DX-Y.NYB ^TNX <GO>"},
        {"Command": "XAU <GO>", "Screen": "Gold Cockpit", "Example": "XAU <GO>"},
        {"Command": "RATES <GO>", "Screen": "Yield Curve", "Example": "RATES <GO>"},
        {"Command": "MACRO <GO>", "Screen": "Macro Dashboard", "Example": "MACRO <GO>"},
        {"Command": "CN <KEYWORD> <GO>", "Screen": "News Intelligence", "Example": "CN FED <GO>"},
        {"Command": "ECO <GO>", "Screen": "Economic Calendar", "Example": "ECO <GO>"},
        {"Command": "ALRT <GO>", "Screen": "Alert Deck", "Example": "ALRT <GO>"},
        {"Command": "PORT <GO>", "Screen": "Portfolio Risk", "Example": "PORT <GO>"},
        {"Command": "EQSC <GO>", "Screen": "Screener", "Example": "EQSC <GO>"},
        {"Command": "CORR <A> <B> <GO>", "Screen": "Correlation", "Example": "CORR GC=F DX-Y.NYB ^TNX <GO>"},
        {"Command": "MAP <GO>", "Screen": "Cross-Asset Map", "Example": "MAP <GO>"},
    ])
    st.dataframe(help_df, use_container_width=True, height=500)
    st.markdown("### WHAT MAKES THIS V75 BUILD MORE BLOOMBERG-LIKE")
    st.dataframe(pd.DataFrame([
        {"Upgrade": "Command-first navigation", "Result": "The command bar controls the active function screen."},
        {"Upgrade": "Security pages", "Result": "Each ticker can show chart, returns, MAs, vol, support/resistance and correlation."},
        {"Upgrade": "Relative value", "Result": "Normalized multi-asset comparison, pair ratio and z-score."},
        {"Upgrade": "XAU cockpit", "Result": "Gold-specific macro score, cross map, alerts and trade checklist."},
        {"Upgrade": "News intelligence", "Result": "RSS headlines tagged by theme, gold read and urgency."},
        {"Upgrade": "Portfolio risk", "Result": "Manual portfolio, exposure, concentration, stop risk and scenario shocks."},
        {"Upgrade": "Dense terminal UI", "Result": "Tighter layout, bottom status bar, function labels and less web-app whitespace."},
    ]), use_container_width=True, height=300)

# ============================================================
# ROUTER
# ============================================================

if active_screen == FUNCTION_SCREENS[0]:
    page_home()
elif active_screen == FUNCTION_SCREENS[1]:
    page_chart()
elif active_screen == FUNCTION_SCREENS[2]:
    page_security()
elif active_screen == FUNCTION_SCREENS[3]:
    page_relative_value()
elif active_screen == FUNCTION_SCREENS[4]:
    page_xau()
elif active_screen == FUNCTION_SCREENS[5]:
    page_rates()
elif active_screen == FUNCTION_SCREENS[6]:
    page_macro()
elif active_screen == FUNCTION_SCREENS[7]:
    page_news()
elif active_screen == FUNCTION_SCREENS[8]:
    page_econ()
elif active_screen == FUNCTION_SCREENS[9]:
    page_alerts()
elif active_screen == FUNCTION_SCREENS[10]:
    page_portfolio()
elif active_screen == FUNCTION_SCREENS[11]:
    page_screener()
elif active_screen == FUNCTION_SCREENS[12]:
    page_corr()
elif active_screen == FUNCTION_SCREENS[13]:
    page_asset_map()
else:
    page_help()

# ============================================================
# FOOTER / STATUS BAR
# ============================================================

st.markdown("---")
st.caption("Built with Streamlit, yfinance, Plotly, RSS feeds, ForexFactory/FairEconomy XML, and Yahoo Finance proxy data.")
st.caption("Free data can be delayed, incomplete, rate-limited, or unavailable. This is an educational/research terminal, not institutional execution infrastructure.")

st.markdown(
    f"""
    <div class="status-bar">
        MARGIN MANOR TERMINAL V75 | ACTIVE: {html.escape(active_screen)} | DATA: FREE/DELAYED | AUTO-REFRESH: {'ON' if auto_refresh_enabled else 'OFF'} {int(auto_refresh_seconds)}s | MARKET TTL: {MARKET_DATA_CACHE_TTL_SECONDS}s | PERIOD: {period} | INTERVAL: {interval} | XAU SCORE: {xau_score}/10 | RISK: {html.escape(regime)} | EVENT: {html.escape(event_regime)} | LAST RERUN SGT: {datetime.now(ZoneInfo('Asia/Singapore')).strftime('%Y-%m-%d %H:%M:%S')}
    </div>
    """,
    unsafe_allow_html=True,
)
