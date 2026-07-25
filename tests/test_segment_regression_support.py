from tests.segment_regression_support import format_landmark_diff, summarize_landmark_diff


def test_summarize_landmark_diff_returns_no_diff_for_equal_lists() -> None:
    expected = [("up", 0, 2), ("down", 3, 5)]
    actual = [("up", 0, 2), ("down", 3, 5)]

    diff = summarize_landmark_diff(expected, actual)

    assert diff.added == []
    assert diff.removed == []
    assert diff.first_mismatch_index is None
    assert diff.start_bi_shift is None
    assert diff.end_bi_shift is None
    assert diff.net_added_count == 0
    assert diff.net_removed_count == 0
    assert diff.added_stop_reasons == []
    assert diff.removed_stop_reasons == []
    assert format_landmark_diff(diff) == "no landmark diff"


def test_summarize_landmark_diff_reports_added_removed_and_order_shift() -> None:
    expected = [("up", 0, 2), ("down", 3, 5), ("up", 6, 8)]
    actual = [("up", 0, 2), ("up", 6, 8), ("down", 9, 11)]

    diff = summarize_landmark_diff(expected, actual)
    summary = format_landmark_diff(diff)

    assert diff.first_mismatch_index == 1
    assert diff.expected_at_mismatch == ("down", 3, 5)
    assert diff.actual_at_mismatch == ("up", 6, 8)
    assert diff.start_bi_shift == 3
    assert diff.end_bi_shift == 3
    assert diff.net_added_count == 1
    assert diff.net_removed_count == 1
    assert diff.added_stop_reasons == [("down", 1)]
    assert diff.removed_stop_reasons == [("down", 1)]
    assert ("down", 9, 11) in diff.added
    assert ("down", 3, 5) in diff.removed
    assert "first mismatch index: 1" in summary
    assert "net added/removed: +1/-1" in summary
    assert "shift(start_bi/end_bi): +3/+3" in summary
    assert "added (1):" in summary
    assert "added stop_reasons:" in summary
    assert "removed (1):" in summary
    assert "removed stop_reasons:" in summary
