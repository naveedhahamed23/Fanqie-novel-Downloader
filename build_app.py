#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python编译脚本
用于GitHub Actions中的可执行文件编译
"""

import subprocess
import sys
import os
import shutil

# 导入编码工具（如果存在）
try:
    from encoding_utils import safe_print, setup_utf8_encoding
    # 确保UTF-8编码设置
    setup_utf8_encoding()
    # 使用安全的print函数
    print = safe_print
except ImportError:
    # 如果编码工具不存在，使用基本的编码设置
    if sys.platform.startswith('win'):
        import locale
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            except locale.Error:
                pass  # 使用默认编码

def build_executable():
    """编译可执行文件"""
    print("Starting build process...")
    
    # 检查build.spec文件
    if os.path.exists("build.spec"):
        print("Using build.spec configuration file")
        cmd = [sys.executable, "-m", "PyInstaller", "build.spec", "--clean", "--noconfirm"]
    else:
        print("build.spec not found, using default configuration")
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile", "--windowed",
            "--name=TomatoNovelDownloader",
            # "--add-data=version.py" + (";" if os.name == "nt" else ":") + ".",  # Removed version.py
            "--hidden-import=bs4",
            "--hidden-import=beautifulsoup4",
            "--hidden-import=fake_useragent",
            "--hidden-import=tqdm",
            "--hidden-import=requests",
            "--hidden-import=urllib3",
            "--hidden-import=ebooklib",
            "--hidden-import=PIL",
            "--hidden-import=PIL.Image",
            "--hidden-import=PIL.ImageTk",
            "gui.py"
        ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        print("Build successful")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("Build failed")
        print(f"Error output: {e.stderr}")
        return False

def check_output():
    """检查编译输出"""
    print("Checking build output...")
    if os.path.exists("dist"):
        files = os.listdir("dist")
        print(f"dist directory contents: {files}")
        
        # 检查可执行文件
        exe_name = "TomatoNovelDownloader.exe" if os.name == "nt" else "TomatoNovelDownloader"
        exe_path = os.path.join("dist", exe_name)
        
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path)
            print(f"Executable created successfully: {exe_name} ({size} bytes)")
            return True
        else:
            print(f"Executable not found: {exe_path}")
            return False
    else:
        print("dist directory does not exist")
        return False

def main():
    """主函数"""
    if build_executable():
        if check_output():
            print("Build completed successfully!")
            return True
        else:
            print("Build output check failed")
            return False
    else:
        print("Build failed")
        return False

if __name__ == "__main__":
    main() 