import sys
sys.path.insert(0, 'src')
from tests.test_segment_regression_00700 import SAMPLE_15M_CSV
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.normalize import normalize_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.bi import identify_bis
from chanlun.segment import _gap_feature_sequence_candidate, _feature_sequence_break, _build_standard_feature_sequence, _feature_element_has_gap, BiDirection

bars = clean_bars(read_bars_from_csv(str(SAMPLE_15M_CSV)))
normalized = normalize_bars(bars)
fractals = filter_consecutive_fractals(identify_fractals(normalized))
bis = identify_bis(fractals, normalized, pending_reverse_mode='any')
for start in range(18, 24):
    reverse_indices = [start+1]
    seq = _build_standard_feature_sequence(bis, reverse_indices)
    print('start', start, 'direction', bis[start].direction.value)
    print(' seq', [(e.high,e.low,e.source_indices) for e in seq])
    print(' gap candidate', _gap_feature_sequence_candidate(bis, reverse_indices, bis[start].direction))
    fb = _feature_sequence_break(bis, reverse_indices, bis[start].direction)
    print(' feature break', fb)
    print('----')
