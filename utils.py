"""
utils.py —— 通用工具（含安全密码生成器）

密码生成使用 os.urandom 做「拒绝采样」，保证每个字符在字符集内均匀分布，无取模偏差。
"""

import os
import string


def generate_password(length: int = 16, use_symbols: bool = True) -> str:
    """
    生成高强度随机密码。
    - 字符集：大小写字母 + 数字；use_symbols 时再加入符号。
    - 采用拒绝采样：逐个随机字节，若落在字符集索引范围内才采用，避免取模偏差。
    """
    chars = list(string.ascii_letters + string.digits)
    if use_symbols:
        chars += list("!@#$%^&*()-_=+[]{};:,.?/")
    n = len(chars)
    out = []
    while len(out) < length:
        b = os.urandom(1)[0]
        if b < n:                      # 拒绝采样：仅在 [0, n) 内才接受
            out.append(chars[b])
    return "".join(out)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
