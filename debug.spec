# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

block_cipher = None

# 收集 fake_useragent 数据文件
fake_useragent_datas = collect_data_files('fake_useragent')

# 分析需要包含的模块
a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[
        # 确保Pillow的二进制文件被包含
    ],
    datas=[
        # ('version.py', '.'),  # Removed version.py file
    ] + fake_useragent_datas,
    hiddenimports=[
        'bs4',
        'fake_useragent',
        'fake_useragent.data',
        'tqdm',
        'requests',
        'urllib3',
        'ebooklib',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'PIL.ImageFile',
        'PIL.ImageFont',
        'PIL.ImageOps',
        'PIL.JpegImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.WebPImagePlugin',
        'PIL._imaging',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.font',
        'tkinter.scrolledtext',
        'threading',
        'json',
        'os',
        'sys',
        'time',
        're',
        'base64',
        'gzip',
        'urllib.parse',
        'concurrent.futures',
        'collections',
        'typing',
        'signal',
        'random',
        'io'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'numpy',
        'scipy',
        'bokeh',
        'h5py',
        'lz4',
        'jinja2',
        'cloudpickle',
        'dask',
        'distributed',
        'fsspec',
        'pyarrow',
        'pytz'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TomatoNovelDownloader-debug',
    debug=True,  # 启用debug模式
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用UPX压缩以避免Windows构建问题
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 启用控制台输出
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
) 