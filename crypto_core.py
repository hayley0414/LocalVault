"""
crypto_core.py —— 安全核心模块（本项目最重要的文件）

职责：
  1. 用 PBKDF2-HMAC-SHA256 从【主密码】派生出加密密钥（32 字节，对应 AES-256）。
     主密码本身绝不写入磁盘明文，只用于这一派生过程。
  2. 用 AES-256-GCM 做「认证加密」：既加密又带 128-bit 认证标签，
     任何对密文的篡改都会在解密时被 GCM 检测到（抛 InvalidTag）。
  3. 数据库盐值(SALT)在创建库时随机生成、长期固定；每次保存数据都重新生成随机 IV(nonce)。
  4. 所有随机数（盐、IV）都由操作系统安全随机源 os.urandom 产生。

⚠️ 安全设计红线（务必牢记）：
  - 主密码、派生密钥、盐值、IV 都【不硬编码】。盐值和 IV 随加密库文件一起保存，
    但盐/IV 本身不是机密（盐防彩虹表，IV 防重放），真正机密只有“主密码”和由它派生的“密钥”，
    二者只存在于运行时的内存中。
  - 派生密钥（self.key）只在 Vault 对象里保存，锁定/退出时从内存丢弃（del + 覆盖）。
  - 不依赖任何网络、不调用任何上传接口。
"""

import os
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# ===== 算法参数（这些是公开参数，不是密钥/密码，可以硬编码）=====
# OWASP 2023 对 PBKDF2-HMAC-SHA256 的建议迭代次数下限为 600,000，
# 迭代越多，暴力破解成本越高（代价是每次解锁稍慢，约 0.3~1 秒，可接受）。
PBKDF2_ITERATIONS = 600_000
KEY_LENGTH = 32          # AES-256 需要 32 字节密钥
SALT_LENGTH = 16         # 盐值长度（字节）
IV_LENGTH = 12           # AES-GCM 推荐 12 字节 nonce（IV）
# 一段固定的“挑战明文”，用主密钥加密后存进库文件，
# 解锁时用它来校验“主密码是否正确”——解密成功且内容匹配即密码正确，
# 这样无需在磁盘上存任何密码相关的明文或哈希。
_MAGIC_VERIFY = b"LOCALVAULT_VERIFY_TOKEN_V1"


def generate_salt() -> bytes:
    """生成随机盐值。os.urandom 使用操作系统提供的加密安全随机源。"""
    return os.urandom(SALT_LENGTH)


def generate_iv() -> bytes:
    """每次加密都生成全新的随机 IV（nonce）。GCM 要求同一个密钥下 IV 不可重复使用。"""
    return os.urandom(IV_LENGTH)


def derive_key(master_password: str, salt: bytes) -> bytes:
    """
    由主密码 + 盐值派生出加密密钥。
    这是“慢哈希”过程：PBKDF2 故意设计得很慢，以大幅提高暴力破解的算力成本。
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(master_password.encode("utf-8"))


def encrypt_bytes(key: bytes, plaintext: bytes):
    """
    AES-256-GCM 加密。
    返回 (iv, ciphertext)，其中 ciphertext 末尾已包含 GCM 认证标签。
    每次调用都使用全新随机 IV。
    """
    iv = generate_iv()
    aes = AESGCM(key)
    # associated_data=None：本库不需要额外的关联认证数据。
    ciphertext = aes.encrypt(iv, plaintext, None)
    return iv, ciphertext


def decrypt_bytes(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    """
    AES-256-GCM 解密。
    若密文被篡改，或 key/iv 不匹配（主密码错误），会抛 InvalidTag 异常。
    """
    aes = AESGCM(key)
    return aes.decrypt(iv, ciphertext, None)


def create_verifier(key: bytes):
    """用当前密钥加密挑战明文，产出 (iv, ct)，用于后续校验主密码。"""
    return encrypt_bytes(key, _MAGIC_VERIFY)


def check_verifier(key: bytes, iv: bytes, ciphertext: bytes) -> bool:
    """尝试用密钥解密挑战串：成功且内容匹配 => 主密码正确；否则错误。"""
    try:
        return decrypt_bytes(key, iv, ciphertext) == _MAGIC_VERIFY
    except InvalidTag:
        return False


# ===== 便捷工具：base64 编解码（用于把二进制密钥材料放进 JSON 文件）=====
def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(text: str) -> bytes:
    return base64.b64decode(text)
