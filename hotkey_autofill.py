"""
hotkey_autofill.py —— 快捷键填充（安全优先）

设计原则（来自需求）：
  1. 不做后台全局钩子（不用 SetWindowsHookEx 监听所有窗口），不自动嗅探窗口/表单。
  2. 只用 Windows 官方「注册热键」机制 RegisterHotKey 监听一个组合键；
     RegisterHotKey 是系统级热键，不是钩子，杀软误报概率远低于 keyboard 库的全局钩子。
  3. 热键触发后，把【当前选中条目】的用户名 + 密码通过 SendInput 模拟键盘输入到
     “当前拥有焦点的窗口”（例如你已经点进去的浏览器输入框）。
  4. 填充前必须确认光标已在目标输入框 —— 软件会在状态栏/托盘反复提示，详见 README。

为什么不用 pyautogui / keyboard 库？
  - keyboard 库底层是全局低级键盘钩子，容易被杀软误报为键盘记录器；
  - 本项目直接用 ctypes 调用 Windows API，零额外依赖、风险更可控。
"""

import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter

# ---- Windows 常量 ----
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_TAB = 0x09

user32 = ctypes.windll.user32


# ---- 键盘输入结构体 ----
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("ki", KEYBDINPUT),
    ]


def _send_unicode_char(ch: str) -> None:
    """用 SendInput 发送一个 Unicode 字符（按下 + 抬起）。"""
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = 0
    inp.ki.wScan = ord(ch)
    inp.ki.dwFlags = KEYEVENTF_UNICODE
    inp.ki.time = 0
    inp.ki.dwExtraInfo = None

    up = INPUT()
    up.type = INPUT_KEYBOARD
    up.ki.wVk = 0
    up.ki.wScan = ord(ch)
    up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
    up.ki.time = 0
    up.ki.dwExtraInfo = None

    arr = (INPUT * 2)(inp, up)
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def _send_vk(vk: int) -> None:
    """发送一个虚拟键码（如 Tab）。"""
    down = INPUT()
    down.type = INPUT_KEYBOARD
    down.ki.wVk = vk
    down.ki.wScan = 0
    down.ki.dwFlags = 0
    down.ki.time = 0
    down.ki.dwExtraInfo = None

    up = INPUT()
    up.type = INPUT_KEYBOARD
    up.ki.wVk = vk
    up.ki.wScan = 0
    up.ki.dwFlags = KEYEVENTF_KEYUP
    up.ki.time = 0
    up.ki.dwExtraInfo = None

    arr = (INPUT * 2)(down, up)
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def send_text(text: str) -> None:
    """把一段文本逐字符模拟键入当前焦点窗口。"""
    for ch in text:
        _send_unicode_char(ch)


def send_credentials(username: str, password: str) -> None:
    """
    填充用户名 + Tab + 密码 到当前焦点输入框。
    约定：先输入用户名，按 Tab 跳到密码框，再输入密码。
    （不同网站表单顺序可能不同，请确认光标位置后再触发。）
    """
    if username:
        send_text(username)
    _send_vk(VK_TAB)        # 切换到下一个输入框（通常是密码框）
    if password:
        send_text(password)


class GlobalHotkey(QAbstractNativeEventFilter):
    """
    注册一个全局热键，并通过 Qt 的原生事件过滤器接收 WM_HOTKEY 消息。
    收到热键消息后调用 on_trigger 回调（由主窗口注入，执行填充）。
    """

    def __init__(self, hotkey_id: int, modifiers: int, vk: int):
        super().__init__()
        self.hotkey_id = hotkey_id
        self.modifiers = modifiers
        self.vk = vk
        self.on_trigger = None
        self._registered = False

    def register(self) -> bool:
        # hWnd=None 表示注册到调用线程的消息队列（配合 Qt 事件循环）
        ret = user32.RegisterHotKey(None, self.hotkey_id, self.modifiers, self.vk)
        self._registered = bool(ret)
        return self._registered

    def unregister(self) -> None:
        if self._registered:
            user32.UnregisterHotKey(None, self.hotkey_id)
            self._registered = False

    def nativeEventFilter(self, eventType, message):
        # Windows 平台事件类型名为 "windows_generic_MSG"
        if eventType == b"windows_generic_MSG":
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    if self.on_trigger:
                        self.on_trigger()
            except Exception:
                pass
        return False, 0
