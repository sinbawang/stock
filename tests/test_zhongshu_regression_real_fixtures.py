from pathlib import Path

from chanlun.zhongshu import identify_zhongshu
from tests.segment_regression_support import identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_00700_30M_CSV = ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260527_to_20260814.csv"
SAMPLE_000591_60M_LONG_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20251210_to_20260618.csv"


def test_00700_30m_segment_zhongshu_keeps_single_active_center_after_multiple_rewrites() -> None:
    segments = identify_segments_from_csv(SAMPLE_00700_30M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")

    assert len(zhongshus) == 1
    current = zhongshus[0]
    assert current.structure_level == "segment"
    assert current.entering_bi_id == 0
    assert current.start_bi_id == 1
    assert current.end_bi_id == 4
    assert current.exit_bi_id is None
    assert current.is_terminated is False
    assert current.superseded_by_zs_id is None
    assert current.is_reabsorbed_by_larger_expansion is False


def test_000591_60m_long_segment_zhongshu_does_not_leave_ghost_center_after_overlap_reuse() -> None:
    segments = identify_segments_from_csv(SAMPLE_000591_60M_LONG_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")

    assert len(segments) == 3
    assert zhongshus == []