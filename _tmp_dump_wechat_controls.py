from pywinauto import Desktop
import psutil
import win32gui
import win32process


def wechat_hwnds():
    targets = {
        proc.pid
        for proc in psutil.process_iter(["name"])
        if proc.info["name"] and proc.info["name"].lower() in {"weixin.exe", "wechatappex.exe"}
    }
    results = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True
        if pid in targets:
            results.append((hwnd, title, pid))
        return True

    win32gui.EnumWindows(callback, 0)
    return results


for hwnd, title, pid in wechat_hwnds():
    print(f"WINDOW hwnd={hwnd} pid={pid} title={title!r}")
    win = Desktop(backend="uia").window(handle=hwnd)
    descendants = win.descendants()
    for ctrl in descendants[:200]:
        try:
            text = ctrl.window_text()
        except Exception:
            text = ""
        try:
            info = ctrl.element_info
            aid = getattr(info, "automation_id", "")
            ctype = getattr(info, "control_type", "")
        except Exception:
            aid = ""
            ctype = ""
        text = (text or "").strip()
        if text or aid in {"chat_input_field", "chat_message_list"}:
            print(f"CTRL type={ctype!r} aid={aid!r} text={text!r}")
