"""
models.py —— 条目数据模型

一个“条目”代表一条需要保管的账号/密钥信息，例如：
  - 网站登录（用户名 + 密码）
  - GitHub Token、API Key
  - SSH 私钥
  - 备案资料（域名、ICP 号、服务商账号等）

字段说明：
  - custom: 自定义键值对，用来存放“非标准”的敏感字段，
            例如 {"GitHub Token": "ghp_xxx", "SSH 私钥": "-----BEGIN...", "备案号": "京ICP备xxx号"}。
  - tags:   标签列表，便于检索。
"""

import time
import uuid
from dataclasses import dataclass, field, asdict


@dataclass
class Entry:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)  # 内部唯一 ID
    title: str = ""            # 标题（必填，列表中显示）
    category: str = "未分类"   # 分类（用于左侧分类筛选）
    url: str = ""              # 网址
    username: str = ""         # 用户名 / 账号
    password: str = ""         # 密码
    note: str = ""             # 备注（明文备注，不敏感时可用）
    custom: dict = field(default_factory=dict)   # 自定义密钥字段（如 Token / SSH / 备案信息）
    tags: list = field(default_factory=list)     # 标签
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Entry":
        # 兼容历史字段缺失：用默认值补齐
        return cls(
            id=d.get("id", uuid.uuid4().hex),
            title=d.get("title", ""),
            category=d.get("category", "未分类"),
            url=d.get("url", ""),
            username=d.get("username", ""),
            password=d.get("password", ""),
            note=d.get("note", ""),
            custom=d.get("custom", {}) or {},
            tags=d.get("tags", []) or [],
            created=d.get("created", time.time()),
            updated=d.get("updated", time.time()),
        )

    def all_searchable_text(self) -> str:
        """拼接所有可搜索文本，供搜索功能使用（小写）。"""
        parts = [self.title, self.category, self.url, self.username, self.note]
        parts += self.tags
        parts += list(self.custom.keys())
        parts += list(self.custom.values())
        return " ".join(str(p) for p in parts).lower()
