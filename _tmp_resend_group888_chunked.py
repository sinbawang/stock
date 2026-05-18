from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from send_wechat_native import send_message


FILES = [
    ROOT / "data" / "_meta" / "group888_fundamental_overview_20260517_174821.txt",
    ROOT / "data" / "_meta" / "000591_太阳能_utility_operator_v1_blended_fundamental_brief_20260517_174828.txt",
    ROOT / "data" / "_meta" / "000651_格力电器_home_appliance_v1_blended_fundamental_brief_20260517_174834.txt",
    ROOT / "data" / "_meta" / "002555_三七互娱_game_content_v1_blended_fundamental_brief_20260517_174840.txt",
    ROOT / "data" / "_meta" / "300124_汇川技术_industrial_automation_v1_blended_fundamental_brief_20260517_174849.txt",
    ROOT / "data" / "_meta" / "600900_长江电力_utility_operator_v1_blended_fundamental_brief_20260517_174855.txt",
    ROOT / "data" / "_meta" / "601328_交通银行_bank_v1_blended_fundamental_brief_20260517_174901.txt",
    ROOT / "data" / "_meta" / "00175_吉利汽车_auto_manufacturing_v1_blended_fundamental_brief_20260517_174932.txt",
    ROOT / "data" / "_meta" / "00700_腾讯_platform_internet_v1_blended_fundamental_brief_20260517_174934.txt",
    ROOT / "data" / "_meta" / "00981_中芯国际_semiconductor_hardtech_v1_blended_fundamental_brief_20260517_174938.txt",
    ROOT / "data" / "_meta" / "01024_快手_platform_internet_v1_blended_fundamental_brief_20260517_174940.txt",
    ROOT / "data" / "_meta" / "01339_中国人保_insurance_v1_blended_fundamental_brief_20260517_174944.txt",
    ROOT / "data" / "_meta" / "02357_中航科工_industrial_automation_v1_fundamental_brief_20260517_174945.txt",
    ROOT / "data" / "_meta" / "03690_美团_platform_internet_v1_blended_fundamental_brief_20260517_174947.txt",
]


def main() -> None:
    for path in FILES:
        print(f"sending {path.name}", flush=True)
        message = path.read_text(encoding="utf-8")
        send_message(
            message=message,
            current_chat_only=True,
            best_effort_current_chat_text=True,
            duplicate_send_window_seconds=300,
        )
        time.sleep(0.8)


if __name__ == "__main__":
    main()
