from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "container_bootstrap_and_run.sh"


def test_shutdown_triggers_backup():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "KLINE_SYNC_BACKUP_ON_STOP" in script_text
    assert "trap" in script_text
    assert "run_backup_once" in script_text


def test_eod_scheduler_enables_catchup_state():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "EOD_SCHEDULER_CATCHUP_ENABLED" in script_text
    assert "EOD_SCHEDULER_STATE_PATH" in script_text
    assert "--catchup" in script_text
    assert "--state-path" in script_text
