import sys
sys.path.insert(0, 'src')
from tests.test_segment_regression_00700 import SAMPLE_15M_CSV
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.normalize import normalize_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.bi import identify_bis
from chanlun.segment import _feature_sequence_break, _gap_feature_sequence_candidate, _build_standard_feature_sequence, BiDirection

bars = clean_bars(read_bars_from_csv(str(SAMPLE_15M_CSV)))
normalized = normalize_bars(bars)
fractals = filter_consecutive_fractals(identify_fractals(normalized))
bis = identify_bis(fractals, normalized, pending_reverse_mode='any')

for start_idx in [18, 19, 20, 21, 22, 23, 24]:
    reverse_indices = [idx for idx in range(start_idx + 1, min(len(bis), start_idx + 6))]
    # try to mimic segment progression with a down segment starting near 22
    # use the current reverse indices as we expect.
    if not reverse_indices:
        continue
    seq = _build_standard_feature_sequence(bis, reverse_indices)
    print('start_idx', start_idx, 'reverse_indices', reverse_indices)
    print('seq', [(e.high, e.low, e.source_indices) for e in seq])
    print('feature_break', _feature_sequence_break(bis, reverse_indices, BiDirection.DOWN))
    print('gap_candidate', _gap_feature_sequence_candidate(bis, reverse_indices, BiDirection.DOWN))
    print('---')
