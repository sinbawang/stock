import sys
from pathlib import Path
root = Path(r"c:\sinba\stock")
sys.path.insert(0, str(root / "src"))
from chanlun.data.hk_minute_fetcher import fetch_hk_minute
rows = fetch_hk_minute("03690", period="60", start="2026-01-01 09:30", end=None, adjust="qfq")
print(len(rows))
print(rows[0]["ts"] if rows else "none")
print(rows[-1]["ts"] if rows else "none")
