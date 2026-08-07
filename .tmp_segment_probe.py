import sys
sys.path.insert(0, 'src')
from tests.test_segment_regression_000591 import SAMPLE_60M_CSV
from tests.test_segment_regression_00700 import SAMPLE_15M_CSV
from tests.segment_regression_support import identify_segments_from_csv

for label, path in [('000591', SAMPLE_60M_CSV), ('00700', SAMPLE_15M_CSV)]:
    segments = identify_segments_from_csv(path)
    print(label)
    for s in segments:
        print((s.direction.value, s.start_bi_id, s.end_bi_id, s.stop_reason, s.is_confirmed, s.norm_bar_range))
    print('---')
