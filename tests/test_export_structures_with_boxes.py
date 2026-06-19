from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chanlun.models import BiDirection, Segment
from export_structures_with_boxes import export_segments


def test_export_segments_writes_expected_columns(tmp_path: Path) -> None:
    path = tmp_path / "segments.csv"
    segments = [
        Segment(
            segment_id=0,
            direction=BiDirection.UP,
            start_bi_id=1,
            end_bi_id=3,
            start_ts=datetime(2024, 1, 1, 10, 30),
            end_ts=datetime(2024, 1, 3, 14, 0),
            start_price=10.0,
            end_price=12.5,
            high=12.5,
            low=9.8,
            norm_bar_range=(4, 12),
            bi_ids=[1, 2, 3],
            is_confirmed=False,
            last_same_extreme=12.5,
            last_reverse_extreme=10.8,
            break_bi_id=4,
            stop_reason="same_direction_not_extending",
        )
    ]

    export_segments(path, segments)

    text = path.read_text(encoding="utf-8-sig")
    assert "segment_id,direction,start_bi_id,end_bi_id,start_ts,end_ts,start_price,end_price,high,low,start_norm_idx,end_norm_idx,bi_ids,last_same_extreme,last_reverse_extreme,break_bi_id,stop_reason,is_confirmed,status,note" in text
    assert "0,up,1,3,2024-01-01 10:30,2024-01-03 14:00,10.0,12.5,12.5,9.8,4,12,\"1,2,3\",12.5,10.8,4,same_direction_not_extending,False,preprocessing,auto_generated" in text