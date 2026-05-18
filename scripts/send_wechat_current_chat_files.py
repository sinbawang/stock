from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from send_wechat_native import send_message


def send_current_chat_files(
    filepaths: list[str | Path],
    *,
    duplicate_send_window_seconds: float = 300.0,
    disable_dedupe: bool = False,
) -> list[Path]:
    resolved_paths = [Path(path).resolve() for path in filepaths]
    if not resolved_paths:
        raise ValueError("filepaths is empty")
    missing = [path for path in resolved_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"file path does not exist: {missing[0]}")

    send_message(
        contact=None,
        message=None,
        filepaths=[str(path) for path in resolved_paths],
        current_chat_only=True,
        duplicate_send_window_seconds=duplicate_send_window_seconds,
        disable_dedupe=disable_dedupe,
    )
    return resolved_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one or more files to the WeChat chat that is already open in the foreground.",
    )
    parser.add_argument("files", nargs="+", help="One or more file paths to send")
    parser.add_argument(
        "--disable-dedupe",
        action="store_true",
        help="Disable short-window duplicate-send protection for retries",
    )
    parser.add_argument(
        "--duplicate-send-window-seconds",
        type=float,
        default=300.0,
        help="Skip duplicate sends within this many seconds; set to 0 to disable",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resolved_paths = send_current_chat_files(
        args.files,
        duplicate_send_window_seconds=args.duplicate_send_window_seconds,
        disable_dedupe=args.disable_dedupe,
    )
    print("Attempted current-chat file send:")
    for path in resolved_paths:
        print(path)


if __name__ == "__main__":
    main()