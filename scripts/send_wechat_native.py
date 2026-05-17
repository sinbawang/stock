from __future__ import annotations

import argparse
import time
from io import BytesIO
from pathlib import Path

import pyperclip
import pywintypes
import win32api
import win32con
import win32clipboard
import win32gui
import win32process
import psutil
from PIL import Image


WINDOW_ATTACH_RETRIES = 3
WINDOW_ATTACH_RETRY_DELAY_SECONDS = 0.8
SEARCH_RESULTS_SETTLE_SECONDS = 1.0
SEARCH_RESULT_SELECTION_STEP_SECONDS = 0.2
CHAT_SWITCH_SETTLE_SECONDS = 1.5
WINDOW_FOREGROUND_RETRIES = 5
WINDOW_FOREGROUND_RETRY_DELAY_SECONDS = 0.2
UIA_SEND_SETTLE_SECONDS = 0.6
UIA_SEND_VERIFY_RETRIES = 5
UIA_MAX_MESSAGE_CHARS = 500


def _wechat_process_names() -> set[str]:
    return {"weixin.exe", "wechatappex.exe"}


def _wechat_pids() -> set[int]:
    return {
        proc.pid
        for proc in psutil.process_iter(["name"])
        if proc.info["name"] and proc.info["name"].lower() in _wechat_process_names()
    }


def _is_wechat_window(hwnd: int) -> bool:
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid in _wechat_pids()


def _ensure_wechat_foreground(hwnd: int) -> None:
    last_error: Exception | None = None
    for _ in range(WINDOW_FOREGROUND_RETRIES):
        foreground = win32gui.GetForegroundWindow()
        if foreground == hwnd and _is_wechat_window(foreground):
            return
        try:
            win32gui.ShowWindow(hwnd, 5)
            win32gui.SetForegroundWindow(hwnd)
        except pywintypes.error as exc:
            last_error = exc
        time.sleep(WINDOW_FOREGROUND_RETRY_DELAY_SECONDS)
    if last_error is not None:
        raise RuntimeError("微信窗口未成功置前") from last_error
    raise RuntimeError("微信窗口未成功置前")


def _get_wechat_window_spec():
    try:
        from pywinauto import Desktop
    except Exception as exc:
        raise RuntimeError("pywinauto 不可用，无法启用安全 UIA 发送") from exc
    return Desktop(backend="uia").window(title="微信")


def _split_message_chunks(message: str, max_chars: int = UIA_MAX_MESSAGE_CHARS) -> list[str]:
    text = message.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        lines = [line.rstrip() for line in paragraph.splitlines() if line.strip()]
        line_chunk = ""
        for line in lines:
            line_candidate = f"{line_chunk}\n{line}" if line_chunk else line
            if len(line_candidate) <= max_chars:
                line_chunk = line_candidate
                continue
            if line_chunk:
                chunks.append(line_chunk)
            line_chunk = line
        if line_chunk:
            current = line_chunk

    if current:
        chunks.append(current)
    return chunks


def _message_list_contains(message_list, text: str) -> bool:
    return any(text in item for item in message_list.texts())


def _send_text_via_uia_current_chat(message: str) -> None:
    if not message:
        raise ValueError("message 不能为空")

    win = _get_wechat_window_spec()
    hwnd = win.wrapper_object().handle
    _ensure_wechat_foreground(hwnd)

    edit = win.child_window(auto_id="chat_input_field", control_type="Edit").wrapper_object()
    send_btn = win.child_window(title="发送", control_type="Button").wrapper_object()
    message_list = win.child_window(auto_id="chat_message_list", control_type="List").wrapper_object()

    chunks = _split_message_chunks(message)
    if not chunks:
        raise ValueError("message 不能为空")

    for chunk in chunks:
        before = message_list.texts()
        edit.set_focus()
        edit.set_edit_text("")
        edit.set_edit_text(chunk)
        send_btn.click_input()

        verified = False
        for _ in range(UIA_SEND_VERIFY_RETRIES):
            time.sleep(UIA_SEND_SETTLE_SECONDS)
            after = message_list.texts()
            if _message_list_contains(message_list, chunk) and after != before:
                verified = True
                break
        if not verified:
            raise RuntimeError("UIA 发送后未在当前会话消息列表中确认到文本")


def find_wechat_window() -> int:
    targets = _wechat_pids()
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
    _ensure_wechat_foreground(hwnd)
    time.sleep(0.6)
    return win32gui.GetWindowRect(hwnd)


def click_ratio(rect: tuple[int, int, int, int], rx: float, ry: float) -> None:
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    x = left + int(width * rx)
    y = top + int(height * ry)
    original_pos = win32api.GetCursorPos()
    try:
        win32api.SetCursorPos((x, y))
        time.sleep(0.15)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.35)
    finally:
        win32api.SetCursorPos(original_pos)


def tap(vk_code: int) -> None:
    win32api.keybd_event(vk_code, 0, 0, 0)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)


def hotkey(*vk_codes: int) -> None:
    for code in vk_codes:
        win32api.keybd_event(code, 0, 0, 0)
    for code in reversed(vk_codes):
        win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 0)


def send_shortcut(hwnd: int | None = None) -> None:
    if hwnd is not None:
        _ensure_wechat_foreground(hwnd)
    tap(win32con.VK_RETURN)
    time.sleep(0.5)


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


def send_files(filepaths: list[str], hwnd: int | None = None) -> None:
    if not filepaths:
        return
    image_suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
    if len(filepaths) == 1 and Path(filepaths[0]).suffix.lower() in image_suffixes:
        copy_image_to_clipboard(filepaths[0])
        time.sleep(0.15)
        hotkey(win32con.VK_CONTROL, ord("V"))
        time.sleep(1.2)
        send_shortcut(hwnd)
        return

    copy_files_to_clipboard(filepaths)
    time.sleep(0.15)
    hotkey(win32con.VK_CONTROL, ord("V"))
    time.sleep(1.2)
    send_shortcut(hwnd)


def _is_retryable_wechat_window_error(exc: Exception) -> bool:
    if isinstance(exc, RuntimeError):
        return "未找到微信主窗口" in str(exc)
    if isinstance(exc, pywintypes.error):
        return bool(exc.args) and exc.args[0] == 1400
    return False


def _focus_chat_input(
    contact: str | None = None,
    result_index: int = 1,
    visible_row_index: int | None = None,
    current_chat_only: bool = False,
    allow_search_switch: bool = False,
) -> None:
    last_exc: Exception | None = None
    for attempt in range(WINDOW_ATTACH_RETRIES):
        try:
            hwnd = find_wechat_window()
            rect = activate_window(hwnd)
            switch_chat(
                rect,
                contact=contact,
                result_index=result_index,
                visible_row_index=visible_row_index,
                current_chat_only=current_chat_only,
                allow_search_switch=allow_search_switch,
            )
            _ensure_wechat_foreground(hwnd)
            click_ratio(rect, 0.67, 0.90)
            return
        except Exception as exc:
            if not _is_retryable_wechat_window_error(exc) or attempt == WINDOW_ATTACH_RETRIES - 1:
                raise
            last_exc = exc
            time.sleep(WINDOW_ATTACH_RETRY_DELAY_SECONDS)
    if last_exc is not None:
        raise last_exc


def switch_chat(
    rect: tuple[int, int, int, int],
    contact: str | None = None,
    result_index: int = 1,
    visible_row_index: int | None = None,
    current_chat_only: bool = False,
    allow_search_switch: bool = False,
) -> None:
    if current_chat_only:
        return

    if visible_row_index is not None:
        visible_row_y = 0.155 + max(visible_row_index - 1, 0) * 0.097
        click_ratio(rect, 0.17, visible_row_y)
        time.sleep(2.0)
        return

    if allow_search_switch and contact:
        click_ratio(rect, 0.17, 0.085)
        hotkey(win32con.VK_CONTROL, ord("A"))
        tap(win32con.VK_BACK)
        type_by_clipboard(contact)
        time.sleep(SEARCH_RESULTS_SETTLE_SECONDS)

        # Use keyboard navigation rather than a fixed click position because
        # WeChat search result layouts vary between versions and window sizes.
        for _ in range(max(result_index, 1)):
            tap(win32con.VK_DOWN)
            time.sleep(SEARCH_RESULT_SELECTION_STEP_SECONDS)
        tap(win32con.VK_RETURN)
        time.sleep(CHAT_SWITCH_SETTLE_SECONDS)
        return

    raise RuntimeError("默认已禁用自动搜索切会话。请使用 --current-chat-only，或明确提供 --visible-row-index。")


def send_to_current_chat(
    message: str | None = None,
    filepaths: list[str] | None = None,
    hwnd: int | None = None,
) -> None:
    if message:
        hotkey(win32con.VK_CONTROL, ord("A"))
        tap(win32con.VK_BACK)
        type_by_clipboard(message)
        send_shortcut(hwnd)

    if filepaths:
        send_files(filepaths, hwnd=hwnd)


def send_message(
    contact: str | None = None,
    message: str | None = None,
    result_index: int = 1,
    visible_row_index: int | None = None,
    filepaths: list[str] | None = None,
    current_chat_only: bool = False,
    allow_search_switch: bool = False,
) -> None:
    if current_chat_only and message and not filepaths:
        _send_text_via_uia_current_chat(message)
        return

    hwnd = find_wechat_window()
    if message:
        _focus_chat_input(
            contact=contact,
            result_index=result_index,
            visible_row_index=visible_row_index,
            current_chat_only=current_chat_only,
            allow_search_switch=allow_search_switch,
        )
        send_to_current_chat(message=message, filepaths=None, hwnd=hwnd)

    if filepaths:
        for filepath in filepaths:
            _focus_chat_input(
                contact=contact,
                result_index=result_index,
                visible_row_index=visible_row_index,
                current_chat_only=current_chat_only,
                allow_search_switch=allow_search_switch,
            )
            send_to_current_chat(message=None, filepaths=[filepath], hwnd=hwnd)


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