import win32gui
import win32process
import psutil

targets = {
    proc.pid
    for proc in psutil.process_iter(["name"])
    if proc.info["name"] and proc.info["name"].lower() in {"weixin.exe", "wechatappex.exe"}
}
rows = []

def callback(hwnd, _):
    if not win32gui.IsWindowVisible(hwnd):
        return True
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid in targets:
        rows.append((hwnd, win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd)))
    return True

win32gui.EnumWindows(callback, 0)
for hwnd, cls, title in rows:
    print(hwnd, cls, title)
