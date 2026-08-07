import sys
sys.path.insert(0, 'src')
from tests.test_segment_regression_00700 import SAMPLE_15M_CSV
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.normalize import normalize_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.bi import identify_bis
from chanlun.segment import _feature_sequence_break, _gap_feature_sequence_candidate, _evaluate_pending_gap_candidate, _reclaims_transition_back_to_prior_segment, _reverse_breaks_last_reverse_extreme, _same_direction_extends, _segment_extremes, _forms_initial_segment, BiDirection

bars = clean_bars(read_bars_from_csv(str(SAMPLE_15M_CSV)))
normalized = normalize_bars(bars)
fractals = filter_consecutive_fractals(identify_fractals(normalized))
bis = identify_bis(fractals, normalized, pending_reverse_mode='any')

start_idx = 22
initial = bis[start_idx:start_idx + 3]
direction = initial[0].direction
cursor = start_idx + 3
end_idx = start_idx + 2
reverse_indices = [start_idx + 1]
last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
pending_gap_break_idx = None
gap_false_locked = False

print('start direction', direction)
for step in range(10):
    if cursor >= len(bis):
        break
    reverse_bi = bis[cursor]
    print('cursor', cursor, 'bi', reverse_bi.bi_id, 'direction', reverse_bi.direction, 'high/low', reverse_bi.high, reverse_bi.low)
    if reverse_bi.direction == direction:
        print('unexpected same')
        break
    reverse_indices.append(cursor)

    prev_same_dir_idx = cursor - 1
    prev_prev_same_dir_idx = cursor - 3
    if (
        prev_same_dir_idx >= start_idx
        and prev_prev_same_dir_idx >= start_idx
        and bis[prev_same_dir_idx].direction == direction
        and bis[prev_prev_same_dir_idx].direction == direction
        and (
            (direction == BiDirection.UP and bis[prev_same_dir_idx].high <= bis[prev_prev_same_dir_idx].high)
            or (direction == BiDirection.DOWN and bis[prev_same_dir_idx].low >= bis[prev_prev_same_dir_idx].low)
        )
    ):
        print('our targeted rule triggered at cursor', cursor)
        break

    if cursor + 1 >= len(bis):
        feature_break = _feature_sequence_break(bis, reverse_indices, direction)
        print('at end, feature_break', feature_break)
        break

    same_dir_bi = bis[cursor + 1]
    print('same_dir_bi', same_dir_bi.bi_id, same_dir_bi.direction, same_dir_bi.high, same_dir_bi.low)
    if same_dir_bi.direction != direction:
        print('slot not filled')
        break

    gap_candidate_idx = _gap_feature_sequence_candidate(bis, reverse_indices, direction)
    print('gap_candidate_idx', gap_candidate_idx)
    if gap_candidate_idx is not None:
        pending_gap_outcome, is_delayed_true, resolved_end_idx, resolved_break_idx, resolved_stop_reason = _evaluate_pending_gap_candidate(bis, gap_candidate_idx)
        print('pending_gap_outcome', pending_gap_outcome, 'resolved_stop_reason', resolved_stop_reason, 'resolved_break_idx', resolved_break_idx)
        if pending_gap_outcome is True:
            print('pending gap confirmed break')
            break

    feature_break = _feature_sequence_break(bis, reverse_indices, direction)
    print('feature_break', feature_break)
    if feature_break is not None:
        print('feature break break')
        break

    if _reverse_breaks_last_reverse_extreme(direction, reverse_bi, last_reverse_extreme):
        print('reverse_breaks_last_reverse_extreme true')
        break

    if direction == BiDirection.UP:
        print('same_dir_bi.high <= last_same_extreme', same_dir_bi.high, last_same_extreme)
        if same_dir_bi.high <= last_same_extreme:
            print('same direction not extending')
            break
        last_reverse_extreme = reverse_bi.low
        last_same_extreme = same_dir_bi.high
    else:
        print('same_dir_bi.low >= last_same_extreme', same_dir_bi.low, last_same_extreme)
        if same_dir_bi.low >= last_same_extreme:
            print('same direction not extending')
            break
        last_reverse_extreme = reverse_bi.high
        last_same_extreme = same_dir_bi.low

    end_idx = cursor + 1
    cursor += 2
    print('updated last extremes', last_same_extreme, last_reverse_extreme)
