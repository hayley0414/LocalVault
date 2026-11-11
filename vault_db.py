"""
vault_db.py —— 加密数据库读写

数据库文件（例如 vault.enc）本质是一个 JSON，结构如下：
{
  "version": 1,
  "kdf": "PBKDF2-HMAC-SHA256",
  "iterations": 600000,
  "salt":  "<base64 盐值，创建库时随机生成，长期固定>",
  "verify_iv":  "<base64>",
  "verify_ct":  "<base64  用主密钥加密的挑战串，用于校验主密码>",
  "data_iv":    "<base64  每次保存都重新随机>",
  "data_ct":    "<base64  加密后的【全部条目 JSON】>"
}

安全要点：
  - 整库（所有条目）一次性加密成一个密文块。只要主密码不泄露，落盘文件就是一堆密文。
  - 盐值随文件保存（非机密，作用是让相同密码派生出不同密钥，防彩虹表/预计算）。
  - 每次保存都用新的随机 IV，避免“相同明文 -> 相同密文”的泄露。
  - 保存采用“先写临时文件 + os.replace 原子替换”，防止写到一半程序崩溃导致库文件损坏。
"""

import os
import json
import time

from crypto_core import (
    derive_key, generate_salt, encrypt_bytes, decrypt_bytes,
    create_verifier, check_verifier, b64encode, b64decode,
    PBKDF2_ITERATIONS,
)
from models import Entry


class VaultError(Exception):
    """库文件相关错误基类。"""


class WrongPassword(VaultError):
    """主密码错误（解密校验失败）。"""


class Vault:
    """
    加密保险库。持有内存中的派生密钥 self.key（仅运行时存在）。
    """

    def __init__(self, path: str, key: bytes, salt: bytes, iterations: int, entries=None):
        self.path = path
        self.key = key            # 32 字节派生密钥，仅存内存，绝不落盘
        self.salt = salt
        self.iterations = iterations
        self.entries = entries or []

    # ------------------------------------------------------------------ #
    # 创建 / 打开
    # ------------------------------------------------------------------ #
    @classmethod
    def create(cls, path: str, master_password: str) -> "Vault":
        """首次使用：创建新的加密库。"""
        salt = generate_salt()                      # 随机盐
        key = derive_key(master_password, salt)     # 派生密钥
        vault = cls(path, key, salt, PBKDF2_ITERATIONS, [])
        vault.save()
        return vault

    @classmethod
    def open_with_key(cls, path: str, key: bytes) -> "Vault":
        """
        已知派生密钥时打开库（用于导入备份校验 / 导入后用同一主密码重载）。
        不重新派生，直接用给定 key 解密并校验。
        """
        if not os.path.exists(path):
            raise VaultError("数据库文件不存在。")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not check_verifier(key, b64decode(data["verify_iv"]), b64decode(data["verify_ct"])):
            raise WrongPassword("该文件的主密码与当前保险库不一致。")
        iv = b64decode(data["data_iv"])
        ct = b64decode(data["data_ct"])
        plaintext = decrypt_bytes(key, iv, ct)
        entries = [Entry.from_dict(e) for e in json.loads(plaintext)]
        return cls(path, key, b64decode(data["salt"]), int(data["iterations"]), entries)

    @classmethod
    def open(cls, path: str, master_password: str) -> "Vault":
        """用主密码打开已有库；密码错误抛 WrongPassword。"""
        if not os.path.exists(path):
            raise VaultError("数据库文件不存在，请先创建。")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        salt = b64decode(data["salt"])
        key = derive_key(master_password, salt)

        # 用挑战串校验主密码是否正确（解密失败即密码错）
        if not check_verifier(key, b64decode(data["verify_iv"]), b64decode(data["verify_ct"])):
            raise WrongPassword("主密码错误，无法解密保险库。")

        # 解密真正的条目数据
        iv = b64decode(data["data_iv"])
        ct = b64decode(data["data_ct"])
        plaintext = decrypt_bytes(key, iv, ct)
        entries = [Entry.from_dict(e) for e in json.loads(plaintext)]
        return cls(path, key, salt, int(data["iterations"]), entries)

    # ------------------------------------------------------------------ #
    # 持久化
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        """把当前所有条目加密写回磁盘（原子替换）。"""
        entries_json = json.dumps(
            [e.to_dict() for e in self.entries],
            ensure_ascii=False,
        ).encode("utf-8")

        data_iv, data_ct = encrypt_bytes(self.key, entries_json)
        verify_iv, verify_ct = create_verifier(self.key)

        payload = {
            "version": 1,
            "kdf": "PBKDF2-HMAC-SHA256",
            "iterations": self.iterations,
            "salt": b64encode(self.salt),
            "verify_iv": b64encode(verify_iv),
            "verify_ct": b64encode(verify_ct),
            "data_iv": b64encode(data_iv),
            "data_ct": b64encode(data_ct),
        }

        # 先写临时文件，再原子替换，避免半截写入损坏库
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp_path, self.path)

    # ------------------------------------------------------------------ #
    # 条目 CRUD
    # ------------------------------------------------------------------ #
    def add_entry(self, entry: Entry) -> None:
        entry.updated = time.time()
        self.entries.append(entry)
        self.save()

    def update_entry(self, entry: Entry) -> None:
        entry.updated = time.time()
        for i, e in enumerate(self.entries):
            if e.id == entry.id:
                self.entries[i] = entry
                break
        self.save()

    def delete_entry(self, entry_id: str) -> None:
        self.entries = [e for e in self.entries if e.id != entry_id]
        self.save()

    def get_entry(self, entry_id: str):
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def categories(self) -> list:
        """返回去重后的分类列表（用于左侧筛选）。"""
        return sorted({e.category for e in self.entries if e.category})

    # ------------------------------------------------------------------ #
    # 安全：从内存丢弃密钥与明文
    # ------------------------------------------------------------------ #
    def destroy(self) -> None:
        """
        锁定时调用：尽力从内存清除密钥与条目明文。
        注意：Python 不保证立即覆写内存，但 del + 覆盖可显著降低残留风险；
        真正安全的做法是进程退出。本项目为学习用途，已做“尽力而为”的处理。
        """
        if self.key:
            # 用 0 覆盖密钥内存（best-effort）
            try:
                self.key = b"\x00" * len(self.key)
            except Exception:
                pass
        self.key = None
        self.entries = []
