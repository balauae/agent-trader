"""
build_ticker_db.py — Build ticker→company name database
=========================================================
Uses yfinance to fetch company info for all watchlist tickers
+ common US stocks. Saves to data/tickers.json

Usage: python scripts/build_ticker_db.py
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Core company name mappings — manually curated for common names
COMPANY_NAMES = {
    # Momentum
    "TSLA": "Tesla", "NVDA": "Nvidia", "AMD": "AMD", "MRVL": "Marvell",
    "PLTR": "Palantir", "COIN": "Coinbase", "APP": "Applovin", "HIMS": "Hims Hers",
    "CRWV": "CoreWeave", "ARM": "ARM Holdings", "RKLB": "Rocket Lab",
    "HOOD": "Robinhood", "SOFI": "SoFi", "SOUN": "SoundHound", "RGTI": "Rigetti",
    "SMCI": "Super Micro",
    # Growth
    "AAPL": "Apple", "MSFT": "Microsoft", "META": "Meta", "AMZN": "Amazon",
    "GOOGL": "Google", "GOOG": "Google", "AVGO": "Broadcom", "MU": "Micron",
    "CRWD": "CrowdStrike", "PANW": "Palo Alto", "NFLX": "Netflix",
    "ORCL": "Oracle", "TSM": "TSMC", "NU": "Nu Holdings", "AFRM": "Affirm",
    "SNOW": "Snowflake", "TEAM": "Atlassian", "DOCU": "DocuSign",
    "WDAY": "Workday", "DOCN": "DigitalOcean", "UNH": "UnitedHealth",
    "OKTA": "Okta", "PYPL": "PayPal", "NVO": "Novo Nordisk",
    # Macro
    "GLD": "Gold ETF", "SLV": "Silver ETF", "IBIT": "Bitcoin ETF", "BABA": "Alibaba",
    # Speculative
    "QBTS": "D-Wave Quantum", "APLD": "Applied Digital", "IREN": "IREN",
    "SMR": "NuScale Power", "ALAB": "Astera Labs", "MDB": "MongoDB",
    # Swing
    "AXON": "Axon", "TTD": "Trade Desk", "ZS": "Zscaler", "ADBE": "Adobe",
    # Others commonly mentioned
    "SPY": "S&P 500 ETF", "QQQ": "Nasdaq ETF", "IWM": "Russell 2000",
    "VIX": "Volatility Index", "DIA": "Dow Jones ETF",
    "INTC": "Intel", "IBM": "IBM", "DELL": "Dell", "HPQ": "HP",
    "JPM": "JPMorgan", "BAC": "Bank of America", "GS": "Goldman Sachs",
    "MS": "Morgan Stanley", "WFC": "Wells Fargo", "C": "Citigroup",
    "V": "Visa", "MA": "Mastercard", "UBER": "Uber", "LYFT": "Lyft",
    "ABNB": "Airbnb", "DASH": "DoorDash", "SHOP": "Shopify",
    "SQ": "Block", "ROKU": "Roku", "SPOT": "Spotify",
    "NFLX": "Netflix", "DIS": "Disney", "CMCSA": "Comcast",
    "T": "AT&T", "VZ": "Verizon", "TMUS": "T-Mobile",
    "XOM": "ExxonMobil", "CVX": "Chevron", "COP": "ConocoPhillips",
    "WMT": "Walmart", "TGT": "Target", "COST": "Costco", "AMZN": "Amazon",
    "HD": "Home Depot", "LOW": "Lowe's", "NKE": "Nike",
    "PFE": "Pfizer", "JNJ": "Johnson & Johnson", "MRNA": "Moderna",
    "BNTX": "BioNTech", "ABBV": "AbbVie", "LLY": "Eli Lilly",
}

# Reverse map: company name → ticker (lowercase for matching)
NAME_TO_TICKER = {}
for ticker, name in COMPANY_NAMES.items():
    # Add full name
    NAME_TO_TICKER[name.lower()] = ticker
    # Add first word (e.g. "apple" → AAPL)
    first_word = name.lower().split()[0]
    if first_word not in NAME_TO_TICKER:
        NAME_TO_TICKER[first_word] = ticker

# Save both maps
output = {
    "ticker_to_name": COMPANY_NAMES,
    "name_to_ticker": NAME_TO_TICKER,
}

out_path = Path(__file__).parent.parent / "data" / "tickers.json"
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(json.dumps(output, indent=2))
print(f"✅ Saved {len(COMPANY_NAMES)} tickers to {out_path}")
print(f"✅ {len(NAME_TO_TICKER)} name→ticker mappings")
print("\nSample name lookups:")
for name in ["apple", "nvidia", "tesla", "google", "meta", "microsoft"]:
    print(f"  '{name}' → {NAME_TO_TICKER.get(name, 'NOT FOUND')}")
