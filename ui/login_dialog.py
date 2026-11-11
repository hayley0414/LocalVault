"""
ui/login_dialog.py —— 主密码登录 / 创建对话框

- 若库文件已存在：作为“解锁”界面，校验主密码。
- 若库文件不存在：作为“创建主密码”界面，要求输入两次并满足最短长度。
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt

from vault_db import Vault, WrongPassword, VaultError
from config import MIN_MASTER_PASSWORD_LEN


class LoginDialog(QDialog):
    def __init__(self, vault_path: str, parent=None):
        super().__init__(parent)
        self.vault_path = vault_path
        self.vault = None                      # 解锁/创建成功后填充
        self._creating = not os.path.exists(vault_path)

        self.setWindowTitle("LocalVault · 创建主密码" if self._creating else "LocalVault · 解锁")
        self.setMinimumWidth(380)
        self.setFixedHeight(230 if self._creating else 190)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("🔐 LocalVault 本地密码保险库")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(
            "首次使用，请设置主密码（至少 %d 位，请牢记，忘记无法找回）" % MIN_MASTER_PASSWORD_LEN
            if self._creating else
            "请输入主密码以解锁本地保险库"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 主密码输入
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText("主密码")
        layout.addWidget(self.pw)

        # 确认密码（仅创建时）
        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw2.setPlaceholderText("再次输入主密码")
        if self._creating:
            layout.addWidget(self.pw2)
        else:
            self.pw2.hide()

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #45475a;")
        layout.addWidget(line)

        btn_row = QHBoxLayout()
        self.ok_btn = QPushButton("解锁" if not self._creating else "创建并进入")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        cancel = QPushButton("退出")
        cancel.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

        # 回车即提交
        self.pw.returnPressed.connect(self._on_ok)
        if self._creating:
            self.pw2.returnPressed.connect(self._on_ok)

    def _on_ok(self):
        pw = self.pw.text()
        if not pw:
            QMessageBox.warning(self, "提示", "主密码不能为空。")
            return
        if self._creating:
            if len(pw) < MIN_MASTER_PASSWORD_LEN:
                QMessageBox.warning(self, "提示",
                                    "主密码至少 %d 位，请设置更强的密码。" % MIN_MASTER_PASSWORD_LEN)
                return
            if pw != self.pw2.text():
                QMessageBox.warning(self, "提示", "两次输入的密码不一致。")
                return
            try:
                self.vault = Vault.create(self.vault_path, pw)
            except Exception as e:
                QMessageBox.critical(self, "创建失败", str(e))
                return
        else:
            try:
                self.vault = Vault.open(self.vault_path, pw)
            except WrongPassword:
                QMessageBox.warning(self, "密码错误", "主密码不正确，请重试。")
                self.pw.clear()
                return
            except VaultError as e:
                QMessageBox.critical(self, "打开失败", str(e))
                return
            except Exception as e:
                QMessageBox.critical(self, "打开失败", str(e))
                return
        self.accept()
