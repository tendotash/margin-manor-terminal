"""
Margin Manor V82 — Hosted hourly XAU fundamental analyst bot.
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

    risk_xau_effect = 0
    if risk_regime == "RISK-OFF":
        risk_xau_effect = 3
    elif risk_regime == "RISK-ON":
        risk_xau_effect = -2
    elif risk_score < 0:
        risk_xau_effect = 1
    elif risk_score > 0:
        risk_xau_effect = -1

    composite = int(max(min(round(xau_score * 7 + news_score * 2 + risk_xau_effect * 3 + dot_score), 100), -100))
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
        "record": record,
    }
    client.table("xau_bot_history").upsert(row, on_conflict="hour_key").execute()


def main():
    client = supabase_client()
    record = build_record(client)
    upsert_record(client, record)
    print(json.dumps({"status": "ok", "hour_key": record["hour_key"], "verdict": record["verdict"], "composite": record["composite"]}, indent=2))


if __name__ == "__main__":
    main()
