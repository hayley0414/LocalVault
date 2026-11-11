"""
main.py —— 程序入口

启动流程：
  1. 创建 QApplication，应用暗色主题。
  2. 若加密库不存在 -> 引导创建主密码；否则 -> 循环要求输入主密码解锁。
  3. 解锁成功后进入主窗口。
  4. 装配三大安全模块：剪贴板自动清空、闲置自动锁定、全局填充热键。
  5. 全程不联网、不上传，所有敏感数据只在本机内存与本地加密文件中。

运行方式见 README.md。
"""

import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon

from styles import DARK_STYLE


def resource_path(rel: str) -> str:
    """
    资源路径解析：兼容「开发态（脚本目录）」与「PyInstaller 打包态（_MEIPASS 临时目录）」。
    这样 app.ico 在两种方式下都能被正确找到。
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)
from config import (
    default_vault_path, DEFAULT_DATA_DIR, load_settings,
    HOTKEY_MODIFIERS, HOTKEY_VK,
)
from vault_db import Vault
from clipboard_manager import ClipboardManager
from idle_locker import IdleLocker
from hotkey_autofill import GlobalHotkey
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def ensure_data_dir():
    os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)


def run_login_loop(vault_path: str) -> Vault:
    """
    显示登录/解锁对话框，直到成功解锁或用户退出。
    返回已解锁的 Vault 对象。
    """
    while True:
        dlg = LoginDialog(vault_path)
        code = dlg.exec()
        if code == dlg.DialogCode.Accepted and dlg.vault is not None:
            return dlg.vault
        else:
            # 取消 / 关闭 -> 退出程序，绝不进入主界面
            sys.exit(0)


def main():
    ensure_data_dir()

    app = QApplication(sys.argv)
    app.setApplicationName("LocalVault")
    app.setStyleSheet(DARK_STYLE)
    # 设置应用图标（窗口标题栏 / 任务栏 / 托盘共用）
    app.setWindowIcon(QIcon(resource_path("app.ico")))

    vault_path = default_vault_path()
    vault = run_login_loop(vault_path)

    # ---- 剪贴板安全管理（复制密码 10 秒后自动清空）----
    clipboard = ClipboardManager(clear_seconds=10, parent=app)

    # ---- 主窗口 ----
    window = MainWindow(vault, clipboard)
    window.show()

    # ---- 闲置自动锁定 ----
    settings = load_settings()
    idle = IdleLocker(seconds=settings.get("autolock_seconds", 300), parent=app)
    idle.timeout.connect(window.lock)
    # 设置里修改自动锁定时间后同步
    window.autolock_changed.connect(idle.set_seconds)

    # ---- 全局填充热键（RegisterHotKey，非全局钩子）----
    hotkey = GlobalHotkey(hotkey_id=1, modifiers=HOTKEY_MODIFIERS, vk=HOTKEY_VK)
    if hotkey.register():
        hotkey.on_trigger = window.do_autofill
        app.installNativeEventFilter(hotkey)
    else:
        QMessageBox.warning(
            window, "热键注册失败",
            "填充热键 Ctrl+Alt+F 注册失败（可能被其它程序占用）。\n"
            "你仍可使用主窗口的「填充」按钮（先把光标放到目标输入框）。"
        )

    # 退出时注销热键
    app.aboutToQuit.connect(hotkey.unregister)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
