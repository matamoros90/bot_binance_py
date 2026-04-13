from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
import os
load_dotenv()
KEY = os.getenv("BINANCE_API_KEY")
SEC = os.getenv("BINANCE_SECRET")
client = Client(KEY, SEC, testnet=False)
risk = client.futures_position_information()
for p in risk:
    amt = float(p.get('positionAmt', 0))
    if amt != 0:
        entry = float(p.get('entryPrice', 0))
        pnl = float(p.get('unRealizedProfit', 0))
        mark = float(p.get('markPrice', 0))
        lev = float(p.get('leverage', 1))
        roi = (pnl / (entry * abs(amt) / lev)) * 100 if entry > 0 and lev > 0 else 0
        print(f"{p['symbol']} Size:{amt} PNL:{pnl} ROI:{roi}%")
