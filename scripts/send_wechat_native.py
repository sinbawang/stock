from __future__ import annotations

import argparse
import time
from io import BytesIO
from pathlib import Path

import pyperclip
import win32api
import win32con
import win32clipboard
import win32gui
import win32process
import psutil
from PIL import Image


def find_wechat_window() -> int:
    targets = {
        proc.pid
        for proc in psutil.process_iter(["name"])
        if proc.info["name"] and proc.info["name"].lower() in {"weixin.exe", "wechatappex.exe"}
    }
    matches: list[int] = []

    def callback(hwnd: int, _: int) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid in targets and win32gui.GetWindowText(hwnd):
            matches.append(hwnd)
        return True

    win32gui.EnumWindows(callback, 0)
    if not matches:
        raise RuntimeError("未找到微信主窗口")
    return matches[0]


def activate_window(hwnd: int) -> tuple[int, int, int, int]:
    win32gui.ShowWindow(hwnd, 5)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.6)
    return win32gui.GetWindowRect(hwnd)


def click_ratio(rect: tuple[int, int, int, int], rx: float, ry: float) -> None:
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    x = left + int(width * rx)
    y = top + int(height * ry)
    win32api.SetCursorPos((x, y))
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.35)


def tap(vk_code: int) -> None:
    win32api.keybd_event(vk_code, 0, 0, 0)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)


def hotkey(*vk_codes: int) -> None:
    for code in vk_codes:
        win32api.keybd_event(code, 0, 0, 0)
    for code in reversed(vk_codes):
        win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)


def type_by_clipboard(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.1)
    hotkey(win32con.VK_CONTROL, ord("V"))
    time.sleep(0.35)


def copy_files_to_clipboard(paths: list[str]) -> None:
    resolved = [str(Path(path).resolve()) for path in paths]
    data = ("\0".join(resolved) + "\0\0").encode("utf-16le")
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
    finally:
        win32clipboard.CloseClipboard()


def copy_image_to_clipboard(filepath: str) -> None:
    image = Image.open(filepath).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="BMP")
    dib_data = buffer.getvalue()[14:]
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, dib_data)
    finally:
        win32clipboard.CloseClipboard()


def send_files(filepaths: list[str]) -> None:
    if not filepaths:
        return
    image_suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
    if len(filepaths) == 1 and Path(filepaths[0]).suffix.lower() in image_suffixes:
        copy_image_to_clipboard(filepaths[0])
        time.sleep(0.15)
        hotkey(win32con.VK_CONTROL, ord("V"))
        time.sleep(1.8)
        hotkey(win32con.VK_MENU, ord("S"))
        time.sleep(2.0)
        return

    copy_files_to_clipboard(filepaths)
    time.sleep(0.15)
    hotkey(win32con.VK_CONTROL, ord("V"))
    time.sleep(0.8)
    tap(win32con.VK_RETURN)
    time.sleep(0.5)


def send_message(
    contact: str | None = None,
    message: str | None = None,
    result_index: int = 1,
    visible_row_index: int | None = None,
    filepaths: list[str] | None = None,
    current_chat_only: bool = False,
    allow_search_switch: bool = False,
) -> None:
    hwnd = find_wechat_window()
    rect = activate_window(hwnd)

    if current_chat_only:
        pass
    elif visible_row_index is not None:
        visible_row_y = 0.155 + max(visible_row_index - 1, 0) * 0.097
        click_ratio(rect, 0.17, visible_row_y)
        time.sleep(2.0)
    elif allow_search_switch and contact:
        # Search box in the left session pane.
        click_ratio(rect, 0.17, 0.085)
        hotkey(win32con.VK_CONTROL, ord("A"))
        tap(win32con.VK_BACK)
        type_by_clipboard(contact)
        time.sleep(0.8)

        # Search results start below the search box; each row is roughly uniform.
        result_y = 0.18 + max(result_index - 1, 0) * 0.11
        click_ratio(rect, 0.17, result_y)
        time.sleep(1.0)
    else:
        raise RuntimeError("默认已禁用自动搜索切会话。请使用 --current-chat-only，或明确提供 --visible-row-index。")

    # Message input box in the right chat pane.
    click_ratio(rect, 0.67, 0.90)
    if filepaths:
        send_files(filepaths)

    if message:
        hotkey(win32con.VK_CONTROL, ord("A"))
        tap(win32con.VK_BACK)
        type_by_clipboard(message)

        tap(win32con.VK_RETURN)
        time.sleep(0.2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a WeChat desktop message by native Win32 automation.")
    parser.add_argument("contact", nargs="?", default=None, help="Contact name to search")
    parser.add_argument("message", nargs="?", default=None, help="Text message to send")
    parser.add_argument("--message-file", default=None, help="Path to a UTF-8 text file whose contents will be sent as the message")
    parser.add_argument("--result-index", type=int, default=1, help="1-based search result row to click")
    parser.add_argument("--visible-row-index", type=int, default=None, help="1-based visible session row to click directly")
    parser.add_argument("--current-chat-only", action="store_true", help="Only send to the chat that is already open; do not switch chats")
    parser.add_argument("--allow-search-switch", action="store_true", help="Allow switching chats by search; disabled by default for safety")
    parser.add_argument("--file", dest="files", action="append", default=None, help="File path to paste and send; repeatable")
    args = parser.parse_args()
    message = args.message
    if args.message_file:
        message = Path(args.message_file).read_text(encoding="utf-8")
    if not args.current_chat_only and args.visible_row_index is None and not args.allow_search_switch:
        raise RuntimeError("默认禁止自动切会话。请先手动打开目标聊天并使用 --current-chat-only，或明确提供 --visible-row-index。")
    send_message(
        args.contact,
        message,
        result_index=args.result_index,
        visible_row_index=args.visible_row_index,
        filepaths=args.files,
        current_chat_only=args.current_chat_only,
        allow_search_switch=args.allow_search_switch,
    )
    target = args.contact or "<current-chat>"
    print(f"Attempted to send to {target}: {message or ''}")


if __name__ == "__main__":
    main()