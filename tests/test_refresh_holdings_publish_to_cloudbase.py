from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module_spec = importlib.util.spec_from_file_location(
    "refresh_holdings_publish_to_cloudbase",
    SCRIPTS / "refresh_holdings_publish_to_cloudbase.py",
)
assert module_spec and module_spec.loader
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_parse_args_defaults_include_1200_bar_targets_and_1m_3000(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["refresh_holdings_publish_to_cloudbase.py"])
    args = module.parse_args()

    assert args.day_bars == 1200
    assert args.m60_bars == 1200
    assert args.m30_bars == 1200
    assert args.m15_bars == 1200
    assert args.m5_bars == 1200
    assert args.m1_bars == 3000
    assert args.sync_kline_cache is True
    assert args.kline_cache_cloud_prefix == "stock-kline-cache/latest"


def test_resolve_kline_cache_source_dir_falls_back_to_container_path(tmp_path, monkeypatch):
    fallback_dir = tmp_path / "data" / "stock-kline-cache"
    fallback_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "ROOT", tmp_path)
    args = module.argparse.Namespace(kline_cache_source_dir=str(tmp_path / "data" / "cache" / "kline"))

    resolved = module._resolve_kline_cache_source_dir(args)

    assert resolved == fallback_dir
