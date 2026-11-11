"""
ui/main_window.py —— 主窗口（程序主界面）

布局：
  ┌─────────────────────────────────────────────┐
  │ 工具栏：新增 编辑 删除 | 复制用户名 复制密码  │
  │   复制自定义密钥[▼] 填充 | 备份 导入 设置 锁定 │
  ├───────────────┬─────────────────────────────┤
  │ 搜索框         │  选中条目详情（含复制按钮）  │
  │ 分类筛选[▼]    │                             │
  │ 条目列表       │                             │
  └───────────────┴─────────────────────────────┘
  └─ 状态栏：剪贴板清空提示 / 填充热键提示 / 锁定状态 ─┘
"""

import os
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QLabel, QGroupBox, QMessageBox,
    QFileDialog, QDialog, QSpinBox, QFormLayout, QApplication, QSystemTrayIcon,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from models import Entry
from vault_db import Vault, WrongPassword, VaultError
from config import (
    BACKUP_DIRNAME, HOTKEY_MODIFIERS, HOTKEY_VK,
    load_settings, save_settings, DEFAULT_DATA_DIR,
)
from clipboard_manager import ClipboardManager
from utils import ensure_dir
from hotkey_autofill import send_credentials
from .login_dialog import LoginDialog
from .entry_dialog import EntryDialog


class SettingsDialog(QDialog):
    """设置：闲置自动锁定时间。"""
    def __init__(self, autolock_seconds: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(300)
        layout = QFormLayout(self)
        self.spin = QSpinBox()
        self.spin.setRange(1, 120)
        self.spin.setValue(autolock_seconds // 60)
        self.spin.setSuffix(" 分钟")
        layout.addRow("闲置自动锁定（无操作后）", self.spin)
        btn = QPushButton("保存")
        btn.setDefault(True)
        btn.clicked.connect(self.accept)
        layout.addRow(btn)

    def value_seconds(self) -> int:
        return self.spin.value() * 60


class MainWindow(QMainWindow):
    def __init__(self, vault: Vault, clipboard: ClipboardManager, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.clipboard = clipboard
        self.selected_entry = None
        self._filtered = []          # 当前显示的条目列表
        self._list_map = {}          # list item id -> entry id

        self.setWindowTitle("LocalVault · 本地密码保险库")
        self.resize(900, 600)
        self._setup_tray()
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------ #
    # 托盘图标（用于填充提示，不窃取焦点）
    # ------------------------------------------------------------------ #
    def _setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self)
            app_icon = QApplication.instance().windowIcon()
            if app_icon is not None and not app_icon.isNull():
                self.tray.setIcon(app_icon)
            else:
                self.tray.setIcon(QApplication.style().standardIcon(
                    QApplication.style().StandardPixmap.SP_DialogYesButton))
            self.tray.setToolTip("LocalVault")
            self.tray.show()
            # 启动提示：说明填充前置条件
            self.tray.showMessage(
                "LocalVault 已就绪",
                "填充快捷键 Ctrl+Alt+F：请先把光标放到目标输入框，再触发。",
                QSystemTrayIcon.MessageIcon.Information, 4000,
            )

    # ------------------------------------------------------------------ #
    # 界面搭建
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ===== 工具栏 =====
        toolbar = QHBoxLayout()
        self.btn_add = QPushButton("+ 新增")
        self.btn_edit = QPushButton("编辑")
        self.btn_del = QPushButton("删除")
        self.btn_del.setObjectName("danger")
        self.btn_copy_user = QPushButton("复制用户名")
        self.btn_copy_pw = QPushButton("复制密码")
        self.custom_combo = QComboBox()
        self.btn_copy_custom = QPushButton("复制自定义密钥")
        self.btn_fill = QPushButton("填充 (Ctrl+Alt+F)")
        self.btn_backup = QPushButton("备份")
        self.btn_import = QPushButton("导入备份")
        self.btn_settings = QPushButton("设置")
        self.btn_lock = QPushButton("锁定")
        self.btn_lock.setObjectName("danger")

        for b in (self.btn_add, self.btn_edit, self.btn_del, self.btn_copy_user,
                  self.btn_copy_pw, self.btn_copy_custom, self.btn_fill,
                  self.btn_backup, self.btn_import, self.btn_settings, self.btn_lock):
            toolbar.addWidget(b)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        # ===== 主体：左列表 + 右详情 =====
        body = QHBoxLayout()

        # 左侧
        left = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 搜索标题/网址/用户名/标签/备注...")
        self.search.textChanged.connect(self._refresh)
        self.cat_combo = QComboBox()
        self.cat_combo.addItem("全部分类")
        self.cat_combo.currentTextChanged.connect(self._refresh)
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_select)
        left.addWidget(self.search)
        left.addWidget(self.cat_combo)
        left.addWidget(self.list_widget, 1)

        # 右侧详情
        self.detail = QVBoxLayout()
        self.detail_widget = QWidget()
        self.detail_widget.setLayout(self.detail)
        body.addLayout(left, 0)
        body.addWidget(self.detail_widget, 1)
        root.addLayout(body)

        # ===== 状态栏 =====
        self.statusBar().showMessage(
            "复制内容会保留在剪贴板（不会自动清空，请用完手动清除）｜ 填充热键 Ctrl+Alt+F（先点目标输入框）"
        )

        # ===== 信号连接 =====
        self.btn_add.clicked.connect(self._add)
        self.btn_edit.clicked.connect(self._edit)
        self.btn_del.clicked.connect(self._delete)
        self.btn_copy_user.clicked.connect(lambda: self._copy_field("username"))
        self.btn_copy_pw.clicked.connect(lambda: self._copy_field("password"))
        self.btn_copy_custom.clicked.connect(self._copy_custom)
        self.btn_fill.clicked.connect(self.do_autofill)
        self.btn_backup.clicked.connect(self._backup)
        self.btn_import.clicked.connect(self._import_backup)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_lock.clicked.connect(self.lock)

    # ------------------------------------------------------------------ #
    # 列表 / 详情刷新
    # ------------------------------------------------------------------ #
    def _refresh(self):
        # 分类下拉更新
        cats = self.vault.categories()
        current = self.cat_combo.currentText()
        self.cat_combo.blockSignals(True)
        self.cat_combo.clear()
        self.cat_combo.addItem("全部分类")
        for c in cats:
            self.cat_combo.addItem(c)
        if current in cats:
            self.cat_combo.setCurrentText(current)
        self.cat_combo.blockSignals(False)

        # 过滤
        q = self.search.text().strip().lower()
        cat = self.cat_combo.currentText()
        self._filtered = []
        for e in self.vault.entries:
            if cat != "全部分类" and e.category != cat:
                continue
            if q and q not in e.all_searchable_text():
                continue
            self._filtered.append(e)

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self._list_map = {}
        for e in self._filtered:
            item = QListWidgetItem("%s   ·   %s" % (e.title or "(无标题)", e.username or ""))
            self.list_widget.addItem(item)
            self._list_map[id(item)] = e.id
        self.list_widget.blockSignals(False)

        if self._filtered:
            self.list_widget.setCurrentRow(0)
        else:
            self._clear_detail()

    def _on_select(self, current, _previous):
        if current is None:
            self.selected_entry = None
            self._clear_detail()
            return
        eid = self._list_map.get(id(current))
        self.selected_entry = self.vault.get_entry(eid)
        self._show_detail(self.selected_entry)

    def _clear_detail(self):
        self.selected_entry = None
        self._clear_layout(self.detail)
        self.custom_combo.clear()
        tip = QLabel("没有选中条目。点击「+ 新增」添加，或在左侧选择。")
        tip.setObjectName("hint")
        self.detail.addWidget(tip)

    def _show_detail(self, e: Entry):
        self._clear_layout(self.detail)
        self.custom_combo.clear()

        # 标题
        title = QLabel(e.title or "(无标题)")
        title.setObjectName("title")
        self.detail.addWidget(title)

        meta = QLabel("分类：%s    标签：%s" % (e.category, ", ".join(e.tags) or "—"))
        meta.setObjectName("hint")
        self.detail.addWidget(meta)

        # 各字段 + 复制按钮
        def field_row(label, value, copyable=True, secret=False):
            row = QHBoxLayout()
            lab = QLabel("%s：" % label)
            lab.setFixedWidth(70)
            val = QLineEdit(value)
            val.setReadOnly(True)
            if secret and value:
                val.setEchoMode(QLineEdit.EchoMode.Password)
            row.addWidget(lab)
            row.addWidget(val, 1)
            if copyable and value:
                cb = QPushButton("复制")
                cb.clicked.connect(lambda _, v=value: self.clipboard.copy(v))
                row.addWidget(cb)
            return row

        if e.url:
            self.detail.addLayout(field_row("网址", e.url, copyable=False))
        self.detail.addLayout(field_row("用户名", e.username))
        self.detail.addLayout(field_row("密码", e.password, secret=bool(e.password)))

        if e.note:
            note_lab = QLabel("备注：")
            note_lab.setObjectName("hint")
            self.detail.addWidget(note_lab)
            note = QLineEdit(e.note)
            note.setReadOnly(True)
            self.detail.addWidget(note)

        # 自定义密钥字段：每个都带复制按钮，并加入顶部下拉
        if e.custom:
            box = QGroupBox("自定义密钥")
            box_layout = QVBoxLayout(box)
            for k, v in e.custom.items():
                row = QHBoxLayout()
                lab = QLabel("%s：" % k)
                lab.setFixedWidth(120)
                val = QLineEdit(v)
                val.setReadOnly(True)
                if v:
                    val.setEchoMode(QLineEdit.EchoMode.Password)
                row.addWidget(lab)
                row.addWidget(val, 1)
                if v:
                    cb = QPushButton("复制")
                    cb.clicked.connect(lambda _, vv=v: self.clipboard.copy(vv))
                    row.addWidget(cb)
                box_layout.addLayout(row)
                self.custom_combo.addItem(k)
            self.detail.addWidget(box)

        self.detail.addStretch(1)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            else:
                # 嵌套布局
                sub = item.layout()
                if sub:
                    self._clear_layout(sub)

    # ------------------------------------------------------------------ #
    # 条目操作
    # ------------------------------------------------------------------ #
    def _add(self):
        dlg = EntryDialog(categories=self.vault.categories(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.vault.add_entry(dlg.get_entry())
            self._refresh()

    def _edit(self):
        if not self.selected_entry:
            QMessageBox.information(self, "提示", "请先在左侧选择一个条目。")
            return
        dlg = EntryDialog(entry=self.selected_entry, categories=self.vault.categories(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.vault.update_entry(dlg.get_entry())
            self._refresh()

    def _delete(self):
        if not self.selected_entry:
            return
        r = QMessageBox.question(self, "确认删除",
                                 "确定删除「%s」吗？此操作不可恢复。" % self.selected_entry.title)
        if r == QMessageBox.StandardButton.Yes:
            self.vault.delete_entry(self.selected_entry.id)
            self._refresh()

    def _copy_field(self, which):
        if not self.selected_entry:
            QMessageBox.information(self, "提示", "请先选择条目。")
            return
        val = getattr(self.selected_entry, which)
        if not val:
            QMessageBox.information(self, "提示", "该字段为空。")
            return
        self.clipboard.copy(val)
        self.statusBar().showMessage("已复制到剪贴板（不会自动清空，请用完手动清除）。")

    def _copy_custom(self):
        if not self.selected_entry or not self.selected_entry.custom:
            QMessageBox.information(self, "提示", "该条目没有自定义密钥字段。")
            return
        key = self.custom_combo.currentText()
        val = self.selected_entry.custom.get(key)
        if not val:
            return
        self.clipboard.copy(val)
        self.statusBar().showMessage("已复制「%s」到剪贴板（不会自动清空，请用完手动清除）。" % key)

    # ------------------------------------------------------------------ #
    # 填充（快捷键 / 按钮）
    # ------------------------------------------------------------------ #
    def do_autofill(self):
        """
        填充当前选中条目的 用户名 + 密码 到“当前焦点输入框”。
        安全提示：必须先手动把光标放到目标输入框（例如浏览器登录框），
        再触发本功能；本程序不会自动识别表单，也不会监听你的按键。
        """
        if not self.selected_entry:
            QMessageBox.information(self, "提示", "请先在左侧选择一个条目，再执行填充。")
            return
        e = self.selected_entry
        # 如果本窗口正聚焦，先最小化，让目标窗口获得焦点，再发送按键
        if self.isActiveWindow():
            self.showMinimized()
            QTimer.singleShot(300, lambda: self._send(e))
        else:
            self._send(e)

    def _send(self, e: Entry):
        send_credentials(e.username, e.password)
        if hasattr(self, "tray"):
            self.tray.showMessage(
                "已填充", "已向当前输入框发送 用户名+密码，请确认光标位置正确。",
                QSystemTrayIcon.MessageIcon.Information, 3000,
            )

    # ------------------------------------------------------------------ #
    # 备份 / 导入
    # ------------------------------------------------------------------ #
    def _backup(self):
        ensure_dir(os.path.join(DEFAULT_DATA_DIR, BACKUP_DIRNAME))
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(DEFAULT_DATA_DIR, BACKUP_DIRNAME, "vault_%s.enc" % ts)
        try:
            shutil.copy2(self.vault.path, dest)
            QMessageBox.information(self, "备份成功",
                                    "已备份加密库到：\n%s\n\n该文件同样是加密的，可安全离线保存。"
                                    % dest)
        except Exception as ex:
            QMessageBox.critical(self, "备份失败", str(ex))

    def _import_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择加密备份文件",
                                              os.path.join(DEFAULT_DATA_DIR, BACKUP_DIRNAME),
                                              "加密库 (*.enc)")
        if not path:
            return
        # 先用当前密钥验证备份是否用同一主密码创建（不覆盖原库）
        try:
            Vault.open_with_key(path, self.vault.key)
        except WrongPassword:
            QMessageBox.critical(self, "无法导入",
                                 "该备份文件的主密码与当前保险库不一致，无法导入。")
            return
        except Exception as ex:
            QMessageBox.critical(self, "无法导入", "文件解析失败：%s" % ex)
            return

        r = QMessageBox.question(self, "确认导入",
                                 "导入将用该备份覆盖当前保险库，确定继续？")
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.copy2(path, self.vault.path)
            self.vault = Vault.open_with_key(self.vault.path, self.vault.key)
            self._refresh()
            QMessageBox.information(self, "导入成功", "已从备份恢复保险库。")
        except Exception as ex:
            QMessageBox.critical(self, "导入失败", str(ex))

    # ------------------------------------------------------------------ #
    # 设置 / 锁定
    # ------------------------------------------------------------------ #
    def _open_settings(self):
        settings = load_settings()
        dlg = SettingsDialog(settings.get("autolock_seconds", 300), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            secs = dlg.value_seconds()
            settings["autolock_seconds"] = secs
            save_settings(settings)
            # 通知外部（main.py）更新闲置锁定时间
            self.autolock_changed.emit(secs)
            QMessageBox.information(self, "已保存", "闲置自动锁定时间已更新为 %d 分钟。" % (secs // 60))

    def lock(self):
        """锁定：丢弃内存中的密钥与明文，要求重新输入主密码。"""
        self.vault.destroy()        # 尽力清除内存中的密钥/明文
        self.hide()
        dlg = LoginDialog(self.vault.path, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.vault = dlg.vault
            self.show()
            self._refresh()
            self.statusBar().showMessage("已解锁。")
        else:
            # 用户取消解锁 => 直接退出程序（更安全）
            QApplication.quit()

    # 供 main.py 连接：自动锁定时间变更
    autolock_changed = pyqtSignal(int)
