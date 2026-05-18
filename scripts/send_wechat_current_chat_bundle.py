from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from send_wechat_current_chat_files import send_current_chat_files
from send_wechat_current_chat_text import send_current_chat_text_file


def send_current_chat_bundle(
    *,
    message_file: str | Path | None = None,
    files: list[str | Path] | None = None,
    duplicate_send_window_seconds: float = 300.0,
    disable_dedupe: bool = False,
    pause_seconds: float = 0.8,
) -> tuple[Path | None, list[Path]]:
    resolved_message_path: Path | None = None
    resolved_files: list[Path] = []

    if message_file is None and not files:
        raise ValueError("bundle requires at least a message file or one file")

    if message_file is not None:
        resolved_message_path = send_current_chat_text_file(
            message_file,
            duplicate_send_window_seconds=duplicate_send_window_seconds,
            disable_dedupe=disable_dedupe,
        )

    if files:
        if resolved_message_path is not None and pause_seconds > 0:
            time.sleep(pause_seconds)
        resolved_files = send_current_chat_files(
            files,
            duplicate_send_window_seconds=duplicate_send_window_seconds,
            disable_dedupe=disable_dedupe,
        )

    return resolved_message_path, resolved_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a text report and optional files to the WeChat chat that is already open in the foreground.",
    )
    parser.add_argument("--message-file", default=None, help="Optional UTF-8 text file to send first")
    parser.add_argument("--file", dest="files", action="append", default=None, help="Optional file to send after the text; repeatable")
    parser.add_argument("--pause-seconds", type=float, default=0.8, help="Pause between text and file sends when both are present")
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
    message_path, resolved_files = send_current_chat_bundle(
        message_file=args.message_file,
        files=args.files,
        duplicate_send_window_seconds=args.duplicate_send_window_seconds,
        disable_dedupe=args.disable_dedupe,
        pause_seconds=args.pause_seconds,
    )
    if message_path is not None:
        print(f"Attempted current-chat bundle text send from {message_path}")
    if resolved_files:
        print("Attempted current-chat bundle file send:")
        for path in resolved_files:
            print(path)


if __name__ == "__main__":
    main()