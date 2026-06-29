from chanlun_api.app import _normalize_technical_publish_timeframes


def test_normalize_technical_publish_timeframes_preserves_day() -> None:
    assert _normalize_technical_publish_timeframes(["30m", "5m"]) == ["30m", "5m", "day"]


def test_normalize_technical_publish_timeframes_keeps_existing_order() -> None:
    assert _normalize_technical_publish_timeframes(["day", "30m", "5m", "day"]) == ["day", "30m", "5m"]


def test_normalize_technical_publish_timeframes_allows_default_bundle() -> None:
    assert _normalize_technical_publish_timeframes(None) is None