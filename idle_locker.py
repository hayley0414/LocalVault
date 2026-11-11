"""
idle_locker.py —— 闲置超时自动锁定

需求：软件闲置超过设定时间，自动锁定界面（要求重新输入主密码）。

实现：
  - 给 QApplication 安装事件过滤器，捕获键盘/鼠标等用户活动。
  - 每次有活动就重置一个倒计时定时器；超时则发射 timeout 信号。
  - 注意：只监听“本程序窗口内”的活动，不监听系统其它窗口，
    因此不会窥探你在别的软件里的操作，符合“安全优先、不偷窥”的原则。
"""

from PyQt6.QtCore import QObject, QEvent, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication


class IdleLocker(QObject):
    timeout = pyqtSignal()   # 闲置超时信号，由主窗口连接 -> 触发锁定

    def __init__(self, seconds: int = 300, parent: QObject = None):
        super().__init__(parent)
        self.seconds = seconds
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        QApplication.instance().installEventFilter(self)
        self.reset()

    def set_seconds(self, seconds: int) -> None:
        self.seconds = max(10, int(seconds))   # 至少 10 秒，防止误设 0
        self.reset()

    def reset(self) -> None:
        """用户有活动时调用，重置闲置倒计时。"""
        self._timer.start(self.seconds * 1000)

    def _on_timeout(self) -> None:
        self.timeout.emit()

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        # 捕获关键交互事件；故意不包含 MouseMove（否则鼠标一动就重置，等于永不锁定）
        if t in (
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.Wheel,
        ):
            self.reset()
        return super().eventFilter(obj, event)
