# LocalVault —— 纯本地 Windows 密码 / 密钥管理器

> ⚠️ **强制风险声明（务必先读）**
>
> 1. 本项目**仅用于学习研究**，目的是理解「主密码派生 + 认证加密」的工程实现。
> 2. 它的安全性**弱于成熟开源密码管理器（如 KeePassXC）**：缺少硬件密钥支持、缺少内存保护审计、未做侧信道防护、未做自校验完整性之外的更多加固。
> 3. **不要**用它存放资金、支付、银行等高敏感密码；学习练手请使用**假数据**。
> 4. 把源码开源到 GitHub 时，**严禁上传你自己的加密数据库文件（`*.enc` / `.localvault/`）**，本仓库 `.gitignore` 已默认排除它们，请务必确认。
> 5. **主密码一旦忘记，任何人都无法恢复数据**（包括你自己）。请务必牢记。

---

## ① 项目目录结构

```
LocalVault/
├── main.py                 # 程序入口：登录流程 + 装配三大安全模块
├── crypto_core.py          # 安全核心：PBKDF2-HMAC-SHA256 派生 + AES-256-GCM 加解密
├── vault_db.py             # 加密数据库读写（整库 JSON -> 加密文件，原子保存）
├── models.py               # 条目数据模型（标题/分类/网址/用户名/密码/备注/自定义密钥/标签）
├── config.py               # 全局配置（路径、超时、热键等，不含任何机密）
├── utils.py                # 工具：安全随机密码生成器（拒绝采样）
├── styles.py               # 暗色主题 QSS 样式表
├── clipboard_manager.py    # 剪贴板安全管理：复制密码 10 秒后自动清空
├── idle_locker.py          # 闲置超时自动锁定（只监听本程序活动，不偷窥系统）
├── hotkey_autofill.py      # 全局填充热键（RegisterHotKey）+ 模拟键盘输入（SendInput）
├── ui/
│   ├── __init__.py
│   ├── login_dialog.py     # 主密码 创建 / 解锁 对话框
│   ├── entry_dialog.py     # 条目 新增 / 编辑 对话框（含动态自定义密钥字段）
│   └── main_window.py      # 主窗口：列表 / 搜索 / 筛选 / 复制 / 填充 / 备份 / 导入 / 锁定
├── requirements.txt        # 依赖清单（PyQt6 + cryptography，皆免费开源）
├── build.spec              # PyInstaller 打包配置（可选）
├── .gitignore              # 排除加密库 / 打包产物 / 缓存，防误上传
└── README.md               # 本文档
```

运行时数据目录（**默认在用户主目录，与代码分离**）：
```
C:\Users\<你>\.localvault\
├── vault.enc          # 加密数据库（你的全部密码都在这里，密文）
├── backups\           # 加密备份（同样是密文）
└── settings.json      # 非机密设置（仅自动锁定时间）
```

---

## ② 依赖清单与安装

只用两个免费开源库：

| 库 | 用途 | 许可 |
|---|---|---|
| `PyQt6` (>=6.4.0) | GUI 框架 | GPL/LGPL |
| `cryptography` (>=42.0.0) | PBKDF2 派生 + AES-256-GCM | Apache-2.0 / BSD |

安装（建议使用虚拟环境）：

```bash
# 1) 创建并激活虚拟环境（可选但推荐）
python -m venv venv
venv\Scripts\activate        # Windows

# 2) 安装依赖
pip install -r requirements.txt
```

> 无需任何联网步骤，依赖安装好之后程序**全程离线运行**。

---

## ③ 代码说明（全部代码见上述文件，注释详尽，安全相关已重点标注）

- **安全核心 `crypto_core.py`**
  - `derive_key`：PBKDF2-HMAC-SHA256，迭代 **600,000** 次（OWASP 2023 对 SHA-256 的建议下限），从主密码派生 32 字节密钥。**主密码不落盘明文**。
  - `encrypt_bytes` / `decrypt_bytes`：AES-**256**-**GCM** 认证加密，每次加密重新生成随机 12 字节 IV；GCM 自带 128-bit 认证标签，可检测密文被篡改。
  - `create_verifier` / `check_verifier`：用主密钥加密一段固定“挑战串”存进库文件，解锁时解密校验，从而**不保存任何密码相关明文/哈希**即可判断主密码是否正确。
  - 盐值、IV 全部 `os.urandom` 生成，**无硬编码密钥/密码/盐值**。
- **数据库 `vault_db.py`**：整库（全部条目）一次性加密成一个密文块；保存采用「写临时文件 + `os.replace` 原子替换」，防半截写入损坏。
- **剪贴板 `clipboard_manager.py`**：复制密码后启动 10 秒倒计时，且**仅当我们复制的内容仍在剪贴板时才清空**，避免误删你之后手动复制的其它内容。
- **闲置锁定 `idle_locker.py`**：只监听本程序窗口内的键盘/鼠标活动，超时发射锁定信号；**不监听系统其它窗口**，不偷窥。
- **填充 `hotkey_autofill.py`**：使用 Windows 官方 `RegisterHotKey` 注册 `Ctrl+Alt+F`（**不是**全局钩子，杀软误报风险低），触发后用 `SendInput` 把「用户名 + Tab + 密码」输入到**当前焦点输入框**。不做自动表单识别、不嗅探窗口。

---

## ④ 本地运行步骤

```bash
# 激活虚拟环境（若使用）
venv\Scripts\activate

# 运行
python main.py
```

首次运行会要求**设置主密码**（至少 8 位），之后每次打开都需输入主密码解锁。
加密库默认创建在 `C:\Users\<你>\.localvault\vault.enc`。

---

## ⑤ PyInstaller 打包成独立 exe

### 完整命令（推荐）

```bash
# 安装打包工具
pip install pyinstaller

# 一键打包为单文件 exe（无控制台黑窗口）
pyinstaller --noconsole --onefile --name LocalVault main.py
```

或用自带的 `build.spec`：

```bash
pyinstaller build.spec
```

打包完成后，exe 位于 `dist\LocalVault.exe`，可单独拷到别的电脑运行（目标电脑需为 Windows）。

### 避坑说明（重要）

1. **杀软误报**：`cryptography` 的 OpenSSL 扩展 + UPX 压缩可能触发 Windows Defender / 360 等误报为“病毒/木马”。
   - 解决：打包时关闭 UPX（`--noupx`），或在 `build.spec` 设 `upx=False`；必要时把 exe 加入杀软白名单。本项目**不含任何联网/上传代码**，可放心审查。
2. **`--onefile` 启动稍慢**：单文件模式每次运行会解压到临时目录，首次启动慢 1~2 秒，正常现象。
3. **缺少模块**：若运行 exe 报 `ModuleNotFoundError`，重新打包并加 `--hidden-import`，例如：
   ```bash
   pyinstaller --noconsole --onefile --name LocalVault ^
     --hidden-import cryptography.hazmat.backends.openssl ^
     --hidden-import cryptography.hazmat.primitives.ciphers.aead ^
     main.py
   ```
4. **不要对 exe 做数字签名之外的“加壳”**：过度加壳会进一步抬高误报率。
5. **数据安全**：打包后的 exe 仍然读写 `C:\Users\<你>\.localvault\vault.enc`，换电脑时记得**连同这个加密文件一起迁移**（它是密文，可离线保存）。

---

## ⑥ 使用说明（操作速查）

| 功能 | 操作 |
|---|---|
| 新增条目 | 顶部「+ 新增」，填标题/分类/网址/用户名/密码，自定义密钥点「+ 添加自定义字段」 |
| 生成强密码 | 编辑条目的密码框旁点「生成」（20 位，含符号） |
| 编辑 / 删除 | 左侧选中条目 ->「编辑」/「删除」 |
| 搜索 / 筛选 | 顶部搜索框输入关键字；下拉按分类筛选 |
| 一键复制 | 详情区每个字段旁「复制」；或顶部「复制用户名 / 复制密码 / 复制自定义密钥」 |
| 自动清剪贴板 | 复制密码后 **10 秒**自动清空 |
| 填充（快捷键） | 先在浏览器把光标放到登录框 -> 按 **Ctrl+Alt+F**（或点「填充」按钮）。程序会输入「用户名 + Tab + 密码」 |
| 自动锁定 | 闲置达到设定时间（默认 5 分钟）自动锁定，需重新输入主密码 |
| 锁定 | 随时点「锁定」 |
| 备份 | 点「备份」-> 生成带时间戳的加密备份到 `backups/` |
| 导入备份 | 点「导入备份」-> 选 `.enc` 文件（须与主库同一主密码）-> 覆盖恢复 |
| 设置 | 点「设置」调整自动锁定时间（分钟） |

> **填充前置提醒（务必遵守）**：填充功能**不会**自动识别表单。请**先手动点击目标输入框、确认光标已就位**，再触发快捷键；否则内容可能填错地方。本程序不监听你的按键、不窥探窗口。

---

## ⑦ `.gitignore`（已内置，防误上传密码库）

已排除：`*.enc`、`.localvault/`、`backups/`、`dist/`、`build/`、`.spec`、`__pycache__/`、虚拟环境等。
上传前请再次确认：**没有任何 `*.enc` 或 `.localvault/` 被 `git add`**。

---

## ⑧ 从零搭建 GitHub 仓库并上传（分步教程）

> 前提：已安装 Git 并注册 GitHub 账号。再次强调：**不要上传你的 `vault.enc` / `.localvault/`**。

1. **本地初始化仓库**（在项目目录内）：
   ```bash
   cd LocalVault
   git init
   git add .
   git status          # 确认没有 *.enc / .localvault 被加入
   git commit -m "feat: 纯本地密码管理器 LocalVault（PBKDF2 + AES-256-GCM）"
   ```
2. **在 GitHub 新建仓库**：
   - 打开 https://github.com/new
   - 仓库名 `LocalVault`，**不要**勾选 “Add a README”（我们已经有了）
   - 选择 **Private**（私有）更稳妥，或 Public 仅放代码
   - 点 “Create repository”
3. **关联并推送**：
   ```bash
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/LocalVault.git
   git push -u origin main
   ```
4. **（可选）写一份发布说明**：在 README 中标注“学习项目、勿存高敏密码、勿上传密码库”。
5. **后续更新**：
   ```bash
   git add .
   git commit -m "更新说明"
   git push
   ```
6. **安全检查收尾**：在 GitHub 仓库页面 -> Settings -> 用搜索确认仓库里**搜不到 `vault.enc`**；若误传，立即删除文件并考虑**更换主密码**（因为旧库可能已泄露）。

---

## 安全设计小结（给想深入学习的你）

- **威胁模型**：保护的是“设备落入他人之手时，离线无法读取你的密码”。它不防御“你本人在用的电脑上已驻留的恶意软件”（那个层面任何密码管理器都难完全防御）。
- **密钥来源**：主密码 -> PBKDF2(盐, 600k) -> AES-256 密钥；密钥只在内存，锁定/退出即丢弃。
- **加密模式**：AES-256-GCM（认证加密），比“裸 AES-CBC/ECB”安全得多，能防密文篡改。
- **可改进方向（进阶练习）**：内存锁定(`VirtualLock`)、密钥派生迭代数自适应、TOTP、硬件密钥(WebAuthn/QR)、数据库完整性 HMAC、自动云备份的**客户端加密**等。

**再次提醒：学习练手请用假数据，切勿存放真实资金/支付密码。**
