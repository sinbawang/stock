from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from send_wechat_native import send_message


def send_current_chat_text(
    message: str,
    *,
    strict_current_chat: bool = False,
    duplicate_send_window_seconds: float = 300.0,
    disable_dedupe: bool = False,
) -> None:
    if not message.strip():
        raise ValueError("message is empty")

    send_message(
        contact=None,
        message=message,
        current_chat_only=True,
        allow_current_chat_fallback=not strict_current_chat,
        duplicate_send_window_seconds=duplicate_send_window_seconds,
        disable_dedupe=disable_dedupe,
    )


def send_current_chat_text_file(
    message_file: str | Path,
    *,
    strict_current_chat: bool = False,
    duplicate_send_window_seconds: float = 300.0,
    disable_dedupe: bool = False,
) -> Path:
    message_path = Path(message_file).resolve()
    if not message_path.exists():
        raise FileNotFoundError(f"message file does not exist: {message_path}")

    message = message_path.read_text(encoding="utf-8")
    send_current_chat_text(
        message,
        strict_current_chat=strict_current_chat,
        duplicate_send_window_seconds=duplicate_send_window_seconds,
        disable_dedupe=disable_dedupe,
    )
    return message_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a UTF-8 text file to the WeChat chat that is already open in the foreground.",
    )
    parser.add_argument("message_file", help="Path to a UTF-8 text file to send")
    parser.add_argument(
        "--strict-current-chat",
        action="store_true",
        help="Fail fast when strict UIA current-chat verification fails instead of falling back",
    )
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
    message_path = send_current_chat_text_file(
        args.message_file,
        strict_current_chat=args.strict_current_chat,
        duplicate_send_window_seconds=args.duplicate_send_window_seconds,
        disable_dedupe=args.disable_dedupe,
    )
    print(f"Attempted current-chat text send from {message_path}")


if __name__ == "__main__":
    main()