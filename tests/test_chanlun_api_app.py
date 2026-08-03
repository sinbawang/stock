import importlib

module = importlib.import_module("chanlun_api.app")
from chanlun_api.app import _normalize_technical_publish_timeframes


def test_normalize_technical_publish_timeframes_preserves_day() -> None:
    assert _normalize_technical_publish_timeframes(["30m", "5m"]) == ["30m", "5m", "day"]


def test_normalize_technical_publish_timeframes_keeps_existing_order() -> None:
    assert _normalize_technical_publish_timeframes(["day", "30m", "5m", "day"]) == ["day", "30m", "5m"]


def test_normalize_technical_publish_timeframes_allows_default_bundle() -> None:
    assert _normalize_technical_publish_timeframes(None) is None


def test_publish_refresh_request_defaults_to_1200_bars() -> None:
    request = module.PublishRefreshRequest()

    assert request.day_bars == 1200
    assert request.m60_bars == 1200
    assert request.m30_bars == 1200
    assert request.m15_bars == 1200
    assert request.m5_bars == 1200
    assert request.m1_bars == 1200


def test_technical_refresh_request_defaults_to_1200_bars() -> None:
    request = module.TechnicalRefreshRequest()

    assert request.day_bars == 1200
    assert request.m60_bars == 1200
    assert request.m30_bars == 1200
    assert request.m15_bars == 1200
    assert request.m5_bars == 1200
    assert request.m1_bars == 1200


def test_run_publish_refresh_reroutes_intraday_only_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_technical_refresh(request):
        captured["request"] = request
        return {"status": "technical"}

    monkeypatch.setattr(module, "_run_technical_refresh", fake_run_technical_refresh)

    request = module.PublishRefreshRequest(
        market="HK",
        tech_timeframes=["5m", "1m"],
        publish_timeframes=["5m", "1m"],
        skip_build=True,
        skip_upload=True,
    )

    result = module._run_publish_refresh(request)

    assert result == {
        "status": "technical",
        "rerouted_from_publish_refresh": True,
        "generated_timeframes": ["5m", "1m"],
    }
    rerouted = captured["request"]
    assert rerouted.refresh_mode == "m5_intraday"
    assert rerouted.tech_timeframes == ["5m", "1m"]
    assert rerouted.publish_timeframes == ["5m", "1m"]
    assert rerouted.day_bars == 1200
    assert rerouted.m30_bars == 1200
    assert rerouted.m5_bars == 1200
    assert rerouted.m1_bars == 1200


def test_run_publish_refresh_keeps_full_path_when_primary_timeframe_requested(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_regenerate_holdings(args):
        captured["tech_timeframes"] = args.tech_timeframes
        return {"generated_count": 1}

    def fake_publish_build_and_upload(args):
        return {"publish_root": args.publish_root, "latest_dir": "latest", "cloud_prefix": args.cloud_prefix, "published_timeframes": None}

    monkeypatch.setattr(module, "regenerate_holdings", fake_regenerate_holdings)
    monkeypatch.setattr(module, "_publish_build_and_upload", fake_publish_build_and_upload)

    request = module.PublishRefreshRequest(skip_build=True, skip_upload=True, tech_timeframes=["30m", "5m", "1m"])

    result = module._run_publish_refresh(request)

    assert captured["tech_timeframes"] == ("30m", "5m", "1m")
    assert result["regenerated"] is True
    assert result["generated_timeframes"] == ["30m", "5m", "1m"]
    assert result["regeneration_summary"] == {"generated_count": 1}