from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fundamental.services import fetch_and_analyze_hk_blended_fundamentals

result = fetch_and_analyze_hk_blended_fundamentals('00175', name='吉利汽车')
snapshot = result.blended.annual_anchor.snapshot
payload = {
    'dividend_yield': snapshot.dividend_yield,
    'assumptions': list(result.assumptions),
    'warnings': list(result.warnings),
}
(ROOT / 'data' / '_meta' / '_tmp_00175_dividend_probe.json').write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding='utf-8',
)
print('ok')
