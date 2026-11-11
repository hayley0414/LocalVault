"""
ui/entry_dialog.py —— 新增 / 编辑条目对话框

字段：
  标题、分类、网址、用户名、密码、备注、标签
  自定义密钥（动态增删，用于存放 GitHub Token、SSH 私钥、备案信息等“非标准”敏感字段）
"""

from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QGroupBox, QMessageBox, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt

from models import Entry
from utils import generate_password


class EntryDialog(QDialog):
    def __init__(self, entry: Entry = None, categories=None, parent=None):
        super().__init__(parent)
        self.is_edit = entry is not None
        self.entry = entry if entry else Entry()
        self.categories = categories or []
        self._custom_rows = []     # 自定义字段的 (key_edit, value_edit, row_widget) 列表
        self.setWindowTitle("编辑条目" if self.is_edit else "新增条目")
        self.setMinimumWidth(520)
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        main = QVBoxLayout(self)

        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("例如：GitHub / 阿里云 / 个人博客备案")
        form.addRow("标题 *", self.title_edit)

        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("分类，如：社交 / 开发 / 金融 / 备案")
        if self.categories:
            from PyQt6.QtWidgets import QCompleter
            self.category_edit.setCompleter(QCompleter(self.categories))
        form.addRow("分类", self.category_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")
        form.addRow("网址", self.url_edit)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("用户名 / 手机号 / 邮箱")
        form.addRow("用户名", self.username_edit)

        # 密码行：输入框 + 显示/隐藏 + 生成
        pw_row = QHBoxLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("密码（留空表示无密码，仅存其它字段）")
        pw_row.addWidget(self.password_edit, 3)
        self.show_btn = QPushButton("显示")
        self.show_btn.setCheckable(True)
        self.show_btn.toggled.connect(self._toggle_pw_show)
        pw_row.addWidget(self.show_btn, 1)
        self.gen_btn = QPushButton("生成")
        self.gen_btn.clicked.connect(self._generate_pw)
        pw_row.addWidget(self.gen_btn, 1)
        form.addRow("密码", pw_row)

        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(70)
        self.note_edit.setPlaceholderText("备注（可选）")
        form.addRow("备注", self.note_edit)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("多个标签用逗号分隔，如：重要, 工作")
        form.addRow("标签", self.tags_edit)

        main.addLayout(form)

        # ---- 自定义密钥字段组 ----
        custom_box = QGroupBox("自定义密钥（Token / SSH / 备案信息等）")
        custom_layout = QVBoxLayout(custom_box)
        self.custom_container = QWidget()
        self.custom_vbox = QVBoxLayout(self.custom_container)
        self.custom_vbox.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(self.custom_container)

        add_custom_btn = QPushButton("+ 添加自定义字段")
        add_custom_btn.clicked.connect(lambda: self._add_custom_row("", ""))
        custom_layout.addWidget(add_custom_btn)

        # 用滚动区域容纳较多自定义字段
        scroll = QScrollArea()
        scroll.setWidget(custom_box)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(220)
        main.addWidget(scroll)

        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#45475a;")
        main.addWidget(line)

        # ---- 底部按钮 ----
        btn_row = QHBoxLayout()
        save = QPushButton("保存")
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        main.addLayout(btn_row)

    # ------------------------------------------------------------------ #
    def _toggle_pw_show(self, checked: bool):
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.show_btn.setText("隐藏" if checked else "显示")

    def _generate_pw(self):
        pw = generate_password(length=20, use_symbols=True)
        self.password_edit.setText(pw)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.show_btn.setChecked(True)
        self.show_btn.setText("隐藏")

    def _add_custom_row(self, key: str, value: str):
        row = QHBoxLayout()
        k = QLineEdit(key)
        k.setPlaceholderText("字段名，如 GitHub Token / SSH私钥 / 备案号")
        v = QLineEdit(value)
        v.setPlaceholderText("字段值")
        v.setEchoMode(QLineEdit.EchoMode.Password)
        del_btn = QPushButton("删除")
        del_btn.setObjectName("danger")
        del_btn.setFixedWidth(60)
        widget = QWidget()
        r = QHBoxLayout(widget)
        r.setContentsMargins(0, 0, 0, 0)
        r.addWidget(k, 2)
        r.addWidget(v, 3)
        r.addWidget(del_btn, 0)
        self.custom_vbox.addWidget(widget)
        rec = {"key": k, "value": v, "widget": widget}
        del_btn.clicked.connect(lambda: self._remove_custom_row(rec))
        self._custom_rows.append(rec)

    def _remove_custom_row(self, rec):
        self.custom_vbox.removeWidget(rec["widget"])
        rec["widget"].deleteLater()
        self._custom_rows.remove(rec)

    # ------------------------------------------------------------------ #
    def _load(self):
        e = self.entry
        self.title_edit.setText(e.title)
        self.category_edit.setText(e.category)
        self.url_edit.setText(e.url)
        self.username_edit.setText(e.username)
        self.password_edit.setText(e.password)
        self.note_edit.setPlainText(e.note)
        self.tags_edit.setText(", ".join(e.tags))
        for k, v in e.custom.items():
            self._add_custom_row(k, v)

    def _on_save(self):
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "标题不能为空。")
            return
        self.entry.title = title
        self.entry.category = self.category_edit.text().strip() or "未分类"
        self.entry.url = self.url_edit.text().strip()
        self.entry.username = self.username_edit.text().strip()
        self.entry.password = self.password_edit.text()
        self.entry.note = self.note_edit.toPlainText()
        self.entry.tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]

        custom = {}
        for rec in self._custom_rows:
            k = rec["key"].text().strip()
            v = rec["value"].text()
            if k:
                custom[k] = v
        self.entry.custom = custom
        self.accept()

    def get_entry(self) -> Entry:
        return self.entry
