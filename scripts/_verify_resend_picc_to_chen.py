from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.zhongshu import identify_zhongshu

from export_structures_with_boxes import calculate_macd
from run_hk_60m_chanlun_to_wechat import analyze_current_state
from send_wechat_native import send_message


def main() -> None:
    csv_path = ROOT / "data" / "01339_中国人保" / "60m" / "01339_60m_20260101_to_20260425.csv"
    image_path = ROOT / "data" / "01339_中国人保" / "60m" / "01339_60m_20260101_to_20260425_normalized_with_boxes_wechat.jpg"

    raw_bars = clean_bars(read_bars_from_csv(str(csv_path)))
    normalized_bars = normalize_bars(raw_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars)
    zhongshus = identify_zhongshu([bi for bi in bis if bi.is_confirmed])
    macd_points = calculate_macd(raw_bars)
    message = analyze_current_state(raw_bars, bis, zhongshus, macd_points)

    send_message(
        "晨",
        message=message,
        visible_row_index=1,
        filepaths=None,
    )
    send_message(
        "晨",
        message=None,
        visible_row_index=1,
        filepaths=[str(image_path)],
    )
    print("resent formatted text and image to 晨")


if __name__ == "__main__":
    main()