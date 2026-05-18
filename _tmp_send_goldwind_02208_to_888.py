from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from send_wechat_current_chat_bundle import send_current_chat_bundle

log_path = ROOT / "data" / "_meta" / "_tmp_send_goldwind_02208_to_888.log"
message_path = ROOT / "data" / "_meta" / "02208_金风科技_tech_mixed_20260518.txt"
day_jpg = ROOT / "build" / "wechat" / "data" / "02208_金风科技" / "day" / "02208_daily_20250102_to_20260518_normalized_with_boxes_wechat.jpg"
m60_jpg = ROOT / "build" / "wechat" / "data" / "02208_金风科技" / "60m" / "02208_60m_20260109_to_20260518_normalized_with_boxes_wechat.jpg"

log_path.write_text("start\n", encoding="utf-8")
try:
    send_current_chat_bundle(
        message_file=message_path,
        files=[day_jpg, m60_jpg],
        duplicate_send_window_seconds=300,
    )
    log_path.write_text("success\n", encoding="utf-8")
    print("success")
except Exception as exc:
    log_path.write_text(f"error: {exc!r}\n", encoding="utf-8")
    print(f"error: {exc!r}")
    raise
