# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置（可选）。也可直接用命令行，见 README。
# 用法：pyinstaller build.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app.ico', '.')],     # 把图标打进 exe，保证打包后窗口图标正常
    hiddenimports=[
        'crypto_core',
        'vault_db',
        'models',
        'config',
        'utils',
        'styles',
        'clipboard_manager',
        'idle_locker',
        'hotkey_autofill',
        'ui',
        'ui.login_dialog',
        'ui.entry_dialog',
        'ui.main_window',
        # cryptography 的部分后端为按需导入，显式声明避免打包后缺失
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.ciphers.aead',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LocalVault',
    icon='app.ico',               # exe 文件图标
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # 不压缩，降低杀软误报（代价：exe 体积略大）
    runtime_tmpdir=None,
    console=False,             # 不显示黑色控制台窗口（纯 GUI）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
