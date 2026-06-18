"""
Margin Manor V83 — Hosted hourly XAU fundamental analyst bot.
Run with GitHub Actions / Render Cron. Writes one analysis row per hour to Supabase.

Required environment variables:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY  (recommended for cron writes)

Optional:
  BOT_TIMEZONE=Asia/Singapore
"""

import os
import math
import html
import json
import re
import smtplib
from email.mime.text import MIMEText
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import feedparser
import yfinance as yf
from supabase import create_client

BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Asia/Singapore")
TZ = ZoneInfo(BOT_TIMEZONE)
OANDA_PRACTICE_URL = "https://api-fxpractice.oanda.com"
OANDA_LIVE_URL = "https://api-fxtrade.oanda.com"
FED_FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

FALLBACK_DOT_POINTS_2026 = [
    3.875, 3.875, 3.875,
    3.625, 3.625, 3.625, 3.625,
    3.375, 3.375, 3.375, 3.375,
    3.125, 3.125, 3.125, 3.125,
    2.875, 2.875,
    2.625,
    2.125,
]

RSS_FEEDS = [
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC Markets", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("Google Markets", "https://news.google.com/rss/search?q=financial+markets&hl=en-US&gl=US&ceid=US:en"),
    ("Google Fed", "https://news.google.com/rss/search?q=Federal+Reserve+markets+stocks+bonds&hl=en-US&gl=US&ceid=US:en"),
    ("Google Economy", "https://news.google.com/rss/search?q=economy+inflation+stocks+bonds+commodities&hl=en-US&gl=US&ceid=US:en"),
    ("Google Gold", "https://news.google.com/rss/search?q=gold+prices+dollar+yields&hl=en-US&gl=US&ceid=US:en"),
    ("Google Oil", "https://news.google.com/rss/search?q=oil+prices+markets+inflation&hl=en-US&gl=US&ceid=US:en"),
    ("Google Geopolitics", "https://news.google.com/rss/search?q=geopolitical+risk+gold+oil+dollar&hl=en-US&gl=US&ceid=US:en"),
]

DRIVER_SPECS = [
    {"Driver": "Gold Futures", "Ticker": "GC=F", "Weight": 3, "Bullish When Up": True, "Logic": "Gold itself rising is direct XAU strength."},
    {"Driver": "Silver Futures", "Ticker": "SI=F", "Weight": 1, "Bullish When Up": True, "Logic": "Silver rising confirms precious metals demand."},
    {"Driver": "US Dollar", "Ticker": "UUP", "Weight": 2, "Bullish When Up": False, "Logic": "A stronger USD is usually a headwind for gold."},
    {"Driver": "DXY Proxy", "Ticker": "DX-Y.NYB", "Weight": 2, "Bullish When Up": False, "Logic": "DXY strength usually pressures USD-priced gold."},
    {"Driver": "10Y Yield", "Ticker": "^TNX", "Weight": 2, "Bullish When Up": False, "Logic": "Higher yields usually raise opportunity cost for gold."},
    {"Driver": "30Y Yield", "Ticker": "^TYX", "Weight": 1, "Bullish When Up": False, "Logic": "Higher long-end yields can pressure gold."},
    {"Driver": "VIX", "Ticker": "^VIX", "Weight": 1, "Bullish When Up": True, "Logic": "Rising fear can create safe-haven demand for gold."},
    {"Driver": "Nasdaq 100", "Ticker": "^NDX", "Weight": 1, "Bullish When Up": False, "Logic": "Strong risk appetite can reduce defensive gold demand."},
    {"Driver": "Bitcoin", "Ticker": "BTC-USD", "Weight": 1, "Bullish When Up": True, "Logic": "Bitcoin strength can signal speculative liquidity."},
    {"Driver": "Oil", "Ticker": "CL=F", "Weight": 1, "Bullish When Up": True, "Logic": "Oil strength can support inflation-sensitive commodity demand."},
    {"Driver": "Copper", "Ticker": "HG=F", "Weight": 1, "Bullish When Up": True, "Logic": "Copper can reflect commodity/growth impulse."},
]


def clean_env_value(value):
    """Clean common copy/paste formats from GitHub/Streamlit secrets."""
    value = str(value or "").strip()

    # Handles accidental GitHub secret value like:
    # SUPABASE_URL = "https://xxxx.supabase.co"
    if "=" in value and value.split("=", 1)[0].strip().upper().startswith("SUPABASE_"):
        value = value.split("=", 1)[1].strip()

    # Remove surrounding quotes only.
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()

    # Remove accidental whitespace/newlines inside URL/key edges.
    return value.strip()


def supabase_client():
    url = clean_env_value(os.getenv("SUPABASE_URL", ""))
    key = clean_env_value(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")) or clean_env_value(os.getenv("SUPABASE_ANON_KEY", ""))

    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY")

    if not url.startswith("https://") or "supabase.co" not in url:
        raise RuntimeError(f"SUPABASE_URL looks invalid after cleaning: {url!r}")

    print(f"Supabase URL being used: {url}")
    print(f"Supabase key prefix OK: {key[:10]}...")

    return create_client(url, key)


def safe_float(value):
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return np.nan
        return v
    except Exception:
        return np.nan



def fetch_fred_csv_series(series_id, lookback_rows=30):
    """Fetch official FRED public graph CSV data without a paid data source."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        df = pd.read_csv(url)
        if df.empty:
            return pd.DataFrame()
        df = df.rename(columns={df.columns[0]: "Date", df.columns[1]: "Value"})
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Value"] = pd.to_numeric(df["Value"].replace(".", np.nan), errors="coerce")
        return df.dropna(subset=["Date", "Value"]).tail(int(lookback_rows))
    except Exception:
        return pd.DataFrame()


def latest_fred_value(series_id):
    df = fetch_fred_csv_series(series_id, 30)
    if df.empty:
        return np.nan, np.nan, "No data"
    last = safe_float(df["Value"].iloc[-1])
    prev = safe_float(df["Value"].iloc[-2]) if len(df) >= 2 else np.nan
    return last, (last - prev if not np.isnan(prev) else np.nan), df["Date"].iloc[-1].strftime("%Y-%m-%d")


def build_curve_snapshot():
    specs = {"DGS2": "2Y", "DGS5": "5Y", "DGS10": "10Y", "DGS30": "30Y", "DFII10": "10Y real yield", "T10YIE": "10Y breakeven"}
    values = {}
    rows = []
    for sid, label in specs.items():
        val, chg, date = latest_fred_value(sid)
        values[sid] = val
        rows.append({"series": sid, "label": label, "value": None if np.isnan(val) else round(float(val), 3), "change_pp": None if np.isnan(chg) else round(float(chg), 3), "date": date})
    def bps(a, b):
        va, vb = values.get(a, np.nan), values.get(b, np.nan)
        return np.nan if np.isnan(va) or np.isnan(vb) else (va - vb) * 100.0
    curve = {
        "rows": rows,
        "two_ten_bps": None if np.isnan(bps("DGS10", "DGS2")) else round(float(bps("DGS10", "DGS2")), 1),
        "five_thirty_bps": None if np.isnan(bps("DGS30", "DGS5")) else round(float(bps("DGS30", "DGS5")), 1),
        "real_10y": None if np.isnan(values.get("DFII10", np.nan)) else round(float(values["DFII10"]), 3),
        "breakeven_10y": None if np.isnan(values.get("T10YIE", np.nan)) else round(float(values["T10YIE"]), 3),
    }
    # XAU curve score: high/rising real yields are headwind; falling real yields tailwind.
    score = 0
    real_yield = values.get("DFII10", np.nan)
    _, real_yield_chg, _ = latest_fred_value("DFII10")
    breakeven = values.get("T10YIE", np.nan)
    if not np.isnan(real_yield):
        score += -3 if real_yield >= 2.0 else -1 if real_yield >= 1.5 else 1 if real_yield <= 1.0 else 0
    if not np.isnan(real_yield_chg):
        score += -2 if real_yield_chg > 0.03 else 2 if real_yield_chg < -0.03 else 0
    if not np.isnan(breakeven):
        score += 1 if breakeven >= 2.3 else -1 if breakeven <= 1.8 else 0
    curve["xau_curve_score"] = int(max(min(score, 10), -10))
    return curve


def get_oanda_mid_price(instrument="XAU_USD"):
    token = clean_env_value(os.getenv("OANDA_API_TOKEN", ""))
    account_id = clean_env_value(os.getenv("OANDA_ACCOUNT_ID", ""))
    env = clean_env_value(os.getenv("OANDA_ENV", "practice")).lower()
    if not token or not account_id:
        return np.nan, {"source": "OANDA not configured"}
    base = OANDA_LIVE_URL if env == "live" else OANDA_PRACTICE_URL
    try:
        resp = requests.get(f"{base}/v3/accounts/{account_id}/pricing", params={"instruments": instrument}, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if resp.status_code != 200:
            return np.nan, {"source": "OANDA", "status": resp.status_code, "message": resp.text[:180]}
        data = resp.json()
        p = (data.get("prices") or [None])[0]
        if not p:
            return np.nan, {"source": "OANDA", "message": "No price"}
        bid = float(p.get("bids", [{}])[0].get("price"))
        ask = float(p.get("asks", [{}])[0].get("price"))
        return (bid + ask) / 2.0, {"source": "OANDA v20", "bid": bid, "ask": ask, "time": p.get("time", "")}
    except Exception as e:
        return np.nan, {"source": "OANDA", "message": str(e)[:180]}


def get_xau_reference_price():
    price, meta = get_oanda_mid_price()
    if not np.isnan(price):
        return float(price), meta
    change, last = get_change_pct("GC=F")
    if not np.isnan(last):
        return float(last), {"source": "Yahoo GC=F fallback", "change_pct": None if np.isnan(change) else round(float(change), 3)}
    return np.nan, {"source": "No XAU price available"}


def get_change_pct(ticker):
    """Try hourly data first; fall back to daily if Yahoo has no intraday data."""
    for period, interval in [("5d", "1h"), ("1mo", "1d")]:
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False, threads=False)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if "Close" not in df.columns:
                continue
            close = df["Close"].dropna()
            if len(close) < 2:
                continue
            last = safe_float(close.iloc[-1])
            prev = safe_float(close.iloc[-2])
            if np.isnan(last) or np.isnan(prev) or prev == 0:
                continue
            return float((last / prev - 1.0) * 100.0), float(last)
        except Exception:
            continue
    return np.nan, np.nan


def compute_xau_driver_score():
    rows = []
    total = 0
    for spec in DRIVER_SPECS:
        change_pct, last = get_change_pct(spec["Ticker"])
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
        total += contribution
        rows.append({
            "Driver": spec["Driver"],
            "Ticker": spec["Ticker"],
            "Last": None if np.isnan(last) else round(last, 4),
            "Change %": None if np.isnan(change_pct) else round(change_pct, 2),
            "Weight": spec["Weight"],
            "Contribution": int(contribution),
            "Effect on XAU": effect,
            "Logic": spec["Logic"],
        })
    total = int(max(min(total, 10), -10))
    if total >= 4:
        bias = "BULLISH XAU TAILWIND"
        action = "Macro supports gold. Wait for bullish price confirmation before entry."
    elif total <= -4:
        bias = "BEARISH XAU HEADWIND"
        action = "Macro pressures gold. Wait for bearish price confirmation before entry."
    else:
        bias = "MIXED XAU"
        action = "Macro is mixed. Reduce risk or wait for cleaner alignment."
    return total, bias, action, pd.DataFrame(rows)


def lookup_change(cache, ticker):
    if ticker not in cache:
        cache[ticker] = get_change_pct(ticker)[0]
    return cache[ticker]


def compute_risk_regime():
    cache = {}
    score = 0
    signals = []
    spy = lookup_change(cache, "SPY")
    qqq = lookup_change(cache, "QQQ")
    vix = lookup_change(cache, "^VIX")
    dollar = lookup_change(cache, "UUP")
    btc = lookup_change(cache, "BTC-USD")
    tlt = lookup_change(cache, "TLT")
    oil = lookup_change(cache, "CL=F")

    if not np.isnan(spy):
        score += 1 if spy > 0 else -1
        signals.append("SPY positive: equity risk appetite supportive." if spy > 0 else "SPY negative: broad equity pressure.")
    if not np.isnan(qqq):
        score += 1 if qqq > 0 else -1
        signals.append("QQQ positive: growth risk appetite supportive." if qqq > 0 else "QQQ negative: growth/tech pressure.")
    if not np.isnan(vix):
        score += 1 if vix < 0 else -1
        signals.append("VIX falling: fear cooling." if vix < 0 else "VIX rising: fear increasing.")
    if not np.isnan(dollar):
        score += 1 if dollar < 0 else -1
        signals.append("Dollar softer: easier cross-asset conditions." if dollar < 0 else "Dollar stronger: tighter cross-asset pressure.")
    if not np.isnan(btc):
        score += 1 if btc > 0 else -1
        signals.append("Bitcoin positive: speculative liquidity present." if btc > 0 else "Bitcoin negative: speculative liquidity weaker.")
    if not np.isnan(tlt) and not np.isnan(spy):
        if spy < 0 and tlt > 0:
            score -= 1
            signals.append("Stocks down while TLT up: defensive bond bid.")
        elif spy > 0 and tlt < 0:
            score += 1
            signals.append("Stocks up while TLT down: risk-on rotation.")
    if not np.isnan(oil):
        signals.append("Oil up strongly: inflation impulse watch." if oil > 1 else "Oil down strongly: growth/inflation concern watch." if oil < -1 else "Oil move not extreme.")

    if score >= 3:
        return "RISK-ON", score, signals
    if score <= -3:
        return "RISK-OFF", score, signals
    return "MIXED / TRANSITION", score, signals


def tag_news_headline(headline):
    h = headline.lower()
    if any(k in h for k in ["fed", "powell", "fomc", "rate cut", "rate hike", "treasury yield", "yields", "inflation", "cpi", "pce", "jobs", "payroll"]):
        if any(k in h for k in ["higher", "hot", "sticky", "hawkish", "rate hike", "surge", "jumps"]):
            return "Fed / Inflation / Yields", "Headwind", "HIGH", 3
        if any(k in h for k in ["lower", "cool", "dovish", "cut", "falls", "drop"]):
            return "Fed / Inflation / Yields", "Tailwind", "HIGH", 3
        return "Fed / Inflation / Yields", "Volatility", "MEDIUM", 2
    if any(k in h for k in ["gold", "bullion", "xau"]):
        return "Gold Direct", "Volatility", "MEDIUM", 2
    if any(k in h for k in ["war", "attack", "geopolitical", "middle east", "iran", "russia", "ukraine", "tariff"]):
        return "Geopolitical Risk", "Safe-Haven Tailwind", "HIGH", 3
    if any(k in h for k in ["dollar", "dxy", "usd"]):
        if any(k in h for k in ["strong", "rises", "surges", "gains"]):
            return "USD", "Headwind", "HIGH", 3
        if any(k in h for k in ["weak", "falls", "drops", "slides"]):
            return "USD", "Tailwind", "HIGH", 3
        return "USD", "Volatility", "MEDIUM", 2
    if any(k in h for k in ["oil", "crude", "energy"]):
        return "Oil / Inflation", "Volatility", "MEDIUM", 2
    return "General Macro", "Mixed", "LOW", 1


def fetch_rss_news(max_items=100):
    rows = []
    for source, url in RSS_FEEDS:
        try:
            response = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                continue
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                if title:
                    rows.append({"Source": source, "Published": entry.get("published", ""), "Headline": title, "Link": entry.get("link", "")})
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["Headline"]).head(max_items)


def score_news_for_xau(news_df, max_headlines=30):
    if news_df is None or news_df.empty:
        return 0, [], "No RSS/news headlines loaded."
    score = 0
    chosen = []
    for _, row in news_df.head(max_headlines).iterrows():
        headline = str(row.get("Headline", ""))
        theme, gold_read, urgency, urgency_score = tag_news_headline(headline)
        bias_delta = 0
        if "Headwind" in gold_read:
            bias_delta = -2
        elif "Tailwind" in gold_read or "Safe-Haven" in gold_read:
            bias_delta = 2
        if urgency == "HIGH":
            bias_delta *= 1.5
        score += bias_delta
        if len(chosen) < 5 and (urgency in ["HIGH", "MEDIUM"] or bias_delta != 0):
            chosen.append({"Source": str(row.get("Source", "")), "Urgency": urgency, "Theme": theme, "Gold Read": gold_read, "Headline": headline})
    score = int(max(min(round(score), 10), -10))
    if score > 2:
        read = "Headline tape leans XAU tailwind / safe-haven supportive."
    elif score < -2:
        read = "Headline tape leans XAU headwind / USD-yield pressure."
    else:
        read = "Headline tape is mixed or not strongly XAU-directional."
    return score, chosen, read


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
            impact = get_text("impact")
            impact = {"High": "Red", "Medium": "Orange", "Low": "Yellow"}.get(impact, impact)
            rows.append({"Date": get_text("date"), "Time": get_text("time"), "Currency": get_text("country"), "Impact": impact, "Event": get_text("title")})
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def event_risk_score():
    df = fetch_forexfactory_calendar()
    if df.empty:
        return 0, "NO EVENT DATA", []
    # Lightweight fallback: if red/orange USD event appears anywhere in this week's feed, show elevated event risk.
    active = df[(df["Currency"].isin(["USD", "EUR", "GBP", "JPY", "CNY"])) & (df["Impact"].isin(["Red", "Orange"]))].head(10)
    score = 0
    if not active.empty:
        red = int((active["Impact"] == "Red").sum())
        orange = int((active["Impact"] == "Orange").sum())
        score = min(red * 3 + orange * 1, 10)
    regime = "EXTREME EVENT RISK" if score >= 8 else "HIGH EVENT RISK" if score >= 5 else "MODERATE EVENT RISK" if score >= 2 else "LOW EVENT RISK"
    return int(score), regime, active[["Date", "Time", "Currency", "Impact", "Event"]].to_dict("records") if not active.empty else []


def load_dot_median(client):
    try:
        resp = client.table("fomc_dotplot_points").select("projected_rate").eq("target_year", 2026).eq("is_active", True).execute()
        points = [float(r["projected_rate"]) for r in (resp.data or []) if r.get("projected_rate") is not None]
        if points:
            return float(np.median(points))
    except Exception:
        pass
    return float(np.median(FALLBACK_DOT_POINTS_2026))


def get_driver_row(driver_df, pattern):
    if driver_df is None or driver_df.empty:
        return None
    mask = driver_df["Driver"].str.contains(pattern, case=False, na=False) | driver_df["Ticker"].str.contains(pattern, case=False, na=False)
    if not mask.any():
        return None
    return driver_df[mask].iloc[0].to_dict()


def fmt_driver(row):
    if not row:
        return "No data"
    change = row.get("Change %")
    change_txt = "n/a" if change is None or pd.isna(change) else f"{float(change):+.2f}%"
    return f"{row.get('Driver')}: {change_txt}, contribution {row.get('Contribution')}, {row.get('Effect on XAU')}"



def find_latest_fed_sep_sources():
    """Detect official Fed projection-material links from the FOMC calendar page."""
    try:
        r = requests.get(FED_FOMC_CALENDAR_URL, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        html_text = r.text
        links = re.findall(r'href=["\']([^"\']*(?:fomcprojtabl|fomcprojmaterials|projection)[^"\']*)["\']', html_text, flags=re.I)
        cleaned = []
        for link in links:
            if link.startswith("/"):
                link = "https://www.federalreserve.gov" + link
            if link.startswith("http") and link not in cleaned:
                cleaned.append(link)
        return cleaned[-10:]
    except Exception:
        return []


def upsert_fed_sep_monitor(client):
    links = find_latest_fed_sep_sources()
    if not links:
        return
    rows = []
    now = datetime.now(ZoneInfo("UTC")).isoformat()
    for link in links:
        release_date = None
        m = re.search(r'(20\d{6})', link)
        if m:
            raw = m.group(1)
            release_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        rows.append({"source_url": link, "release_date": release_date, "detected_at": now, "status": "detected", "notes": "Official Fed projection-material link detected. Exact dot coordinates are updated only if parseable; otherwise active Supabase dots remain in use."})
    try:
        client.table("fomc_sep_updates").upsert(rows, on_conflict="source_url").execute()
    except Exception:
        pass


def log_notification(client, channel, verdict, message, ok, detail=""):
    try:
        client.table("xau_notification_log").insert({"channel": channel, "verdict": verdict, "message": message[:1000], "success": bool(ok), "detail": detail[:500]}).execute()
    except Exception:
        pass


def send_telegram(text):
    token = clean_env_value(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = clean_env_value(os.getenv("TELEGRAM_CHAT_ID", ""))
    if not token or not chat_id:
        return False, "Telegram not configured"
    try:
        resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        return resp.status_code == 200, resp.text[:250]
    except Exception as e:
        return False, str(e)[:250]


def send_discord(text):
    url = clean_env_value(os.getenv("DISCORD_WEBHOOK_URL", ""))
    if not url:
        return False, "Discord not configured"
    try:
        resp = requests.post(url, json={"content": text[:1900]}, timeout=10)
        return 200 <= resp.status_code < 300, resp.text[:250]
    except Exception as e:
        return False, str(e)[:250]


def send_email_alert(subject, text):
    host = clean_env_value(os.getenv("SMTP_HOST", ""))
    port = int(clean_env_value(os.getenv("SMTP_PORT", "587")) or 587)
    user = clean_env_value(os.getenv("SMTP_USER", ""))
    password = clean_env_value(os.getenv("SMTP_PASSWORD", ""))
    to_addr = clean_env_value(os.getenv("ALERT_EMAIL_TO", ""))
    if not host or not user or not password or not to_addr:
        return False, "Email SMTP not configured"
    try:
        msg = MIMEText(text)
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_addr
        with smtplib.SMTP(host, port, timeout=12) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return True, "sent"
    except Exception as e:
        return False, str(e)[:250]


def maybe_send_notifications(client, record):
    # Avoid spam: one alert per hour_key/channel. Send only high-confidence or extreme event-risk calls.
    should_alert = record.get("confidence") == "HIGH" or record.get("event_regime") == "EXTREME EVENT RISK" or abs(int(record.get("composite", 0))) >= 65
    if not should_alert:
        return
    msg = f"Margin Manor XAU Bot {record['generated_sgt']}\n{record['verdict']} | Confidence: {record['confidence']} | Composite: {record['composite']}\nXAU score: {record['xau_score']}/10 | Risk: {record['risk_regime']} {record['risk_score']} | Event: {record['event_regime']}\nAction: {record['action']}"
    for channel, fn in [("telegram", send_telegram), ("discord", send_discord)]:
        ok, detail = fn(msg)
        if ok or "not configured" not in detail.lower():
            log_notification(client, channel, record["verdict"], msg, ok, detail)
    ok, detail = send_email_alert(f"Margin Manor XAU Bot: {record['verdict']}", msg)
    if ok or "not configured" not in detail.lower():
        log_notification(client, "email", record["verdict"], msg, ok, detail)


def insert_price_snapshot(client, price, meta):
    if np.isnan(price):
        return
    try:
        client.table("xau_price_snapshots").insert({"observed_at": datetime.now(ZoneInfo("UTC")).isoformat(), "xau_price": float(price), "source": str(meta.get("source", "unknown")), "meta": meta}).execute()
    except Exception:
        pass


def update_backtest_outcomes(client, current_price):
    if np.isnan(current_price):
        return
    try:
        resp = client.table("xau_bot_history").select("hour_key, generated_at, record, entry_xau_price, outcome_1h_pct, outcome_4h_pct, outcome_24h_pct").order("generated_at", desc=False).limit(500).execute()
        rows = resp.data or []
    except Exception:
        return
    now_utc = datetime.now(ZoneInfo("UTC"))
    for row in rows:
        rec = row.get("record") if isinstance(row.get("record"), dict) else {}
        entry = row.get("entry_xau_price") or rec.get("entry_xau_price")
        if entry is None:
            continue
        try:
            entry = float(entry)
        except Exception:
            continue
        gen = row.get("generated_at")
        try:
            gen_dt = datetime.fromisoformat(str(gen).replace("Z", "+00:00"))
        except Exception:
            continue
        age_hours = (now_utc - gen_dt).total_seconds() / 3600.0
        updates = {}
        record_updates = {}
        for horizon, col in [(1, "outcome_1h_pct"), (4, "outcome_4h_pct"), (24, "outcome_24h_pct")]:
            if age_hours >= horizon and row.get(col) is None and rec.get(col) is None:
                pct = (float(current_price) / entry - 1.0) * 100.0
                updates[col] = round(float(pct), 4)
                record_updates[col] = round(float(pct), 4)
        if updates:
            rec.update(record_updates)
            updates["record"] = rec
            try:
                client.table("xau_bot_history").update(updates).eq("hour_key", row.get("hour_key")).execute()
            except Exception:
                pass


def build_record(client):
    now_sg = datetime.now(TZ)
    hour_key = now_sg.strftime("%Y-%m-%d %H:00")
    xau_score, xau_bias, xau_action, driver_df = compute_xau_driver_score()
    risk_regime, risk_score, risk_signals = compute_risk_regime()
    event_score, event_regime, next_events = event_risk_score()
    news_df = fetch_rss_news()
    news_score, important_news, news_read = score_news_for_xau(news_df)
    dot_median = load_dot_median(client)
    dot_score = -3 if dot_median >= 3.25 else 2
    curve_snapshot = build_curve_snapshot()
    curve_score = int(curve_snapshot.get("xau_curve_score", 0) or 0)
    xau_ref_price, xau_price_meta = get_xau_reference_price()

    risk_xau_effect = 0
    if risk_regime == "RISK-OFF":
        risk_xau_effect = 3
    elif risk_regime == "RISK-ON":
        risk_xau_effect = -2
    elif risk_score < 0:
        risk_xau_effect = 1
    elif risk_score > 0:
        risk_xau_effect = -1

    composite = int(max(min(round(xau_score * 7 + news_score * 2 + risk_xau_effect * 3 + dot_score + curve_score * 3), 100), -100))
    if composite >= 35:
        verdict = "BULLISH XAU"
        card_class = "bot-card-bull"
        action = "Prefer long setups after sell-side sweep + bullish MSS/CISD. Do not chase without structure confirmation."
    elif composite <= -35:
        verdict = "BEARISH XAU"
        card_class = "bot-card-bear"
        action = "Prefer short setups after buy-side sweep + bearish MSS/CISD. Do not short blindly into displacement without confirmation."
    else:
        verdict = "MIXED / WAIT"
        card_class = "bot-card-wait"
        action = "No clean fundamental edge. Reduce size, wait for clearer driver alignment, or demand very clean price confirmation."

    confidence = "HIGH" if abs(composite) >= 65 and event_regime not in ["HIGH EVENT RISK", "EXTREME EVENT RISK"] else "MEDIUM" if abs(composite) >= 35 else "LOW"
    if event_regime in ["HIGH EVENT RISK", "EXTREME EVENT RISK"]:
        confidence = "LOW / EVENT-RISK OVERRIDE"

    ranked = driver_df.copy()
    ranked["Abs Contribution"] = ranked["Contribution"].abs()
    top_drivers = ranked.sort_values("Abs Contribution", ascending=False).head(5)[["Driver", "Change %", "Contribution", "Effect on XAU", "Logic"]].to_dict("records")

    lines = [
        f"XAU driver score: {xau_score}/10 ({xau_bias}).",
        f"USD layer: {fmt_driver(get_driver_row(driver_df, 'Dollar|DXY'))}.",
        f"Yield layer: {fmt_driver(get_driver_row(driver_df, '10Y'))}; {fmt_driver(get_driver_row(driver_df, '30Y'))}.",
        f"Metals confirmation: {fmt_driver(get_driver_row(driver_df, 'Gold'))}; {fmt_driver(get_driver_row(driver_df, 'Silver'))}.",
        f"Risk regime: {risk_regime}, score {risk_score}. For gold this is {'safe-haven supportive' if risk_xau_effect > 0 else 'risk-appetite headwind' if risk_xau_effect < 0 else 'not directional'}.",
        f"Event risk: {event_regime}, score {event_score}. High event risk reduces conviction even if direction is clear.",
        f"News tape: {news_read}",
        f"FOMC dot plot reference: 2026 median around {dot_median:.3f}% if unchanged; higher-for-longer dots are a structural yield headwind for XAU.",
        f"Advanced yield layer: 2s10s {curve_snapshot.get('two_ten_bps')} bps, 5s30s {curve_snapshot.get('five_thirty_bps')} bps, 10Y real yield {curve_snapshot.get('real_10y')}%, 10Y breakeven {curve_snapshot.get('breakeven_10y')}%. Curve score for XAU: {curve_score}.",
        f"XAU reference price: {('n/a' if np.isnan(xau_ref_price) else round(float(xau_ref_price), 3))} from {xau_price_meta.get('source', 'unknown')}.",
    ]

    return {
        "hour_key": hour_key,
        "generated_sgt": now_sg.strftime("%Y-%m-%d %H:%M:%S"),
        "verdict": verdict,
        "confidence": confidence,
        "composite": composite,
        "card_class": card_class,
        "xau_score": int(xau_score),
        "xau_bias": str(xau_bias),
        "risk_regime": str(risk_regime),
        "risk_score": int(risk_score),
        "event_regime": str(event_regime),
        "event_score": int(event_score),
        "news_score": int(news_score),
        "dot_median": round(dot_median, 3),
        "curve_score": int(curve_score),
        "curve_snapshot": curve_snapshot,
        "entry_xau_price": None if np.isnan(xau_ref_price) else round(float(xau_ref_price), 4),
        "xau_price_meta": xau_price_meta,
        "action": action,
        "lines": lines,
        "top_drivers": top_drivers,
        "important_news": important_news,
        "next_events": next_events,
        "risk_signals": list(risk_signals or [])[:5],
    }


def upsert_record(client, record):
    row = {
        "hour_key": record["hour_key"],
        "generated_sgt": record["generated_sgt"],
        "verdict": record["verdict"],
        "confidence": record["confidence"],
        "composite": int(record["composite"]),
        "xau_score": int(record["xau_score"]),
        "entry_xau_price": record.get("entry_xau_price"),
        "record": record,
    }
    client.table("xau_bot_history").upsert(row, on_conflict="hour_key").execute()


def main():
    client = supabase_client()
    upsert_fed_sep_monitor(client)
    record = build_record(client)
    upsert_record(client, record)
    price = record.get("entry_xau_price")
    price = np.nan if price is None else float(price)
    insert_price_snapshot(client, price, record.get("xau_price_meta", {}))
    update_backtest_outcomes(client, price)
    maybe_send_notifications(client, record)
    print(json.dumps({"status": "ok", "hour_key": record["hour_key"], "verdict": record["verdict"], "composite": record["composite"], "entry_xau_price": record.get("entry_xau_price")}, indent=2))


if __name__ == "__main__":
    main()
