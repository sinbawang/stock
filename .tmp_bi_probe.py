import sys
sys.path.insert(0, 'src')
from tests.test_segment_regression_00700 import SAMPLE_15M_CSV
from tests.segment_regression_support import identify_segments_from_csv
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.normalize import normalize_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.bi import identify_bis

bars = clean_bars(read_bars_from_csv(str(SAMPLE_15M_CSV)))
normalized = normalize_bars(bars)
fractals = filter_consecutive_fractals(identify_fractals(normalized))
bis = identify_bis(fractals, normalized, pending_reverse_mode='any')
for i, bi in enumerate(bis):
    if 14 <= i <= 28:
        print(i, bi.bi_id, bi.direction.value, bi.high, bi.low, bi.is_confirmed, bi.start_ts, bi.end_ts)
