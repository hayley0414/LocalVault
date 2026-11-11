"""
clipboard_manager.py —— 剪贴板安全管理

需求：复制密码到剪贴板后，10 秒自动清空，降低“密码残留在剪贴板被别的程序读到”的风险。

安全细节：
  - 只在我们自己复制的内容【仍然在】剪贴板时才清空，避免误删用户之后手动复制的其它内容。
  - 使用 PyQt6 的剪贴板接口，不依赖任何第三方剪贴板监控工具。
"""

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication


class ClipboardManager(QObject):
    def __init__(self, clear_seconds: int = 10, parent: QObject = None):
        super().__init__(parent)
        self.clipboard = QApplication.clipboard()
        self.clear_seconds = clear_seconds
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)          # 只触发一次
        self._timer.timeout.connect(self._clear)
        self._stored_text = None                 # 记住我们刚复制的内容

    def copy(self, text: str) -> None:
        """复制文本到剪贴板，并启动自动清空倒计时。"""
        if text is None:
            text = ""
        self.clipboard.setText(text)
        self._stored_text = text
        self._timer.start(self.clear_seconds * 1000)

    def _clear(self) -> None:
        """倒计时结束：仅当我们复制的内容还在剪贴板时才清空。"""
        try:
            if self.clipboard.text() == self._stored_text:
                self.clipboard.setText("")       # 清空
        except Exception:
            pass
        self._stored_text = None

    def cancel(self) -> None:
        """取消待清空的定时器（例如用户主动又复制了别的东西）。"""
        self._timer.stop()
        self._stored_text = None
