"""
config.py —— 全局配置

这里只放“非机密”的配置项：文件路径、默认超时、剪贴板清空时间等。
任何密钥 / 密码 / 盐值都不在这里出现。
"""

import os
import json

APP_NAME = "LocalVault"
APP_VERSION = "1.0.0"

# 数据目录：默认放在用户主目录下（与项目代码分离，避免误提交到 GitHub）
DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), ".localvault")
VAULT_FILENAME = "vault.enc"
BACKUP_DIRNAME = "backups"
SETTINGS_FILENAME = "settings.json"

# 默认保险库文件路径
def default_vault_path() -> str:
    return os.path.join(DEFAULT_DATA_DIR, VAULT_FILENAME)

def backup_dir() -> str:
    return os.path.join(DEFAULT_DATA_DIR, BACKUP_DIRNAME)

def settings_path() -> str:
    return os.path.join(DEFAULT_DATA_DIR, SETTINGS_FILENAME)

# 行为默认值
DEFAULT_AUTOLOCK_SECONDS = 300      # 闲置 5 分钟自动锁定
# 复制密码后自动清空剪贴板的秒数；设为 0 表示【永不自动清空】（由用户手动清除）。
CLIPBOARD_CLEAR_SECONDS = 0
MIN_MASTER_PASSWORD_LEN = 8         # 主密码最短长度（创建时强制）

# 填充快捷键：Ctrl + Alt + F（通过 Windows RegisterHotKey 注册，非全局钩子）
HOTKEY_MODIFIERS = 0x0002 | 0x0001 | 0x4000   # MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
HOTKEY_VK = 0x46                                  # 'F'


# ===== 设置读写（不含任何机密，明文 JSON 即可）=====
def load_settings() -> dict:
    path = settings_path()
    if not os.path.exists(path):
        return {"autolock_seconds": DEFAULT_AUTOLOCK_SECONDS}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("autolock_seconds", DEFAULT_AUTOLOCK_SECONDS)
        return data
    except Exception:
        return {"autolock_seconds": DEFAULT_AUTOLOCK_SECONDS}


def save_settings(data: dict) -> None:
    os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
    with open(settings_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
