# -*- coding: utf-8 -*-
"""
自动更新模块
提供基于GitHub Releases的版本检测和自动更新功能
"""

import os
import sys
import json
import time
import shutil
import zipfile
import tempfile
import threading
import subprocess
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

import requests
from packaging import version


class UpdateChecker:
    """版本检测器"""
    
    def __init__(self, github_repo: str, current_version: str):
        """
        初始化更新检测器
        
        Args:
            github_repo: GitHub仓库地址，格式为 'owner/repo'
            current_version: 当前版本号
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self.api_base = "https://api.github.com"
        self.check_interval = 3600  # 检查间隔（秒）
        self.last_check_time = None
        self.cached_release = None
        
    def get_latest_release(self, force_check: bool = False) -> Optional[Dict[str, Any]]:
        """
        获取最新版本信息
        
        Args:
            force_check: 是否强制检查（忽略缓存）
            
        Returns:
            最新版本信息字典，包含版本号、下载链接等
        """
        # 检查缓存
        if not force_check and self.cached_release and self.last_check_time:
            if time.time() - self.last_check_time < self.check_interval:
                return self.cached_release
        
        try:
            url = f"{self.api_base}/repos/{self.github_repo}/releases/latest"
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Tomato-Novel-Downloader'
            }
            token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            
            # 解析版本信息
            release_info = {
                'version': release_data['tag_name'].lstrip('v'),
                'name': release_data['name'],
                'body': release_data['body'],
                'published_at': release_data['published_at'],
                'html_url': release_data['html_url'],
                'assets': []
            }
            
            # 解析下载链接
            for asset in release_data.get('assets', []):
                asset_info = {
                    'name': asset['name'],
                    'size': asset['size'],
                    'download_url': asset['browser_download_url'],
                    'content_type': asset['content_type']
                }
                release_info['assets'].append(asset_info)
            
            # 更新缓存
            self.cached_release = release_info
            self.last_check_time = time.time()
            
            return release_info
            
        except requests.exceptions.RequestException as e:
            print(f"检查更新失败: {e}")
            return None
        except Exception as e:
            print(f"解析版本信息失败: {e}")
            return None
    
    def has_update(self, force_check: bool = False) -> bool:
        """
        检查是否有新版本
        
        Args:
            force_check: 是否强制检查
            
        Returns:
            是否有新版本
        """
        latest_release = self.get_latest_release(force_check)
        if not latest_release:
            return False
        
        try:
            latest_ver = version.parse(latest_release['version'])
            current_ver = version.parse(self.current_version)
            return latest_ver > current_ver
        except Exception:
            return False
    
    def get_update_info(self) -> Optional[Dict[str, Any]]:
        """
        获取更新信息（版本号、更新内容等）
        
        Returns:
            更新信息字典
        """
        if not self.has_update():
            return None
        
        return self.cached_release


class AutoUpdater:
    """自动更新器"""
    
    def __init__(self, github_repo: str, current_version: str):
        """
        初始化自动更新器
        
        Args:
            github_repo: GitHub仓库地址
            current_version: 当前版本号
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self.checker = UpdateChecker(github_repo, current_version)
        self.download_progress = 0
        self.download_total = 0
        self.is_downloading = False
        self.update_callbacks = []
        
    def register_callback(self, callback: Callable):
        """注册更新回调函数"""
        self.update_callbacks.append(callback)
        
    def _notify_callbacks(self, event: str, data: Any = None):
        """通知所有回调函数"""
        for callback in self.update_callbacks:
            try:
                callback(event, data)
            except Exception as e:
                print(f"回调函数执行失败: {e}")
    
    def check_for_updates(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        检查更新
        
        Args:
            force: 是否强制检查
            
        Returns:
            更新信息
        """
        return self.checker.get_update_info() if self.checker.has_update(force) else None
    
    def _get_platform_asset(self, assets: list) -> Optional[Dict[str, Any]]:
        """
        根据平台选择合适的下载文件
        
        Args:
            assets: 资源列表
            
        Returns:
            合适的资源信息
        """
        platform = sys.platform.lower()
        
        # 定义平台关键字
        platform_keywords = {
            'win32': ['windows', 'win', '.exe'],
            'darwin': ['macos', 'mac', 'darwin', '.dmg', '.app'],
            'linux': ['linux', '.appimage', '.deb', '.rpm']
        }
        
        keywords = platform_keywords.get(platform, [])
        
        # 查找匹配的资源
        for asset in assets:
            asset_name_lower = asset['name'].lower()
            for keyword in keywords:
                if keyword in asset_name_lower:
                    return asset
        
        # 如果没有找到平台特定的，尝试查找通用的zip文件
        for asset in assets:
            if asset['name'].lower().endswith('.zip'):
                return asset
        
        return None
    
    def download_update(self, update_info: Dict[str, Any], 
                       progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        下载更新
        
        Args:
            update_info: 更新信息
            progress_callback: 进度回调函数
            
        Returns:
            下载的文件路径
        """
        if self.is_downloading:
            return None
        
        self.is_downloading = True
        self._notify_callbacks('download_start', update_info)
        
        try:
            # 选择合适的下载文件
            asset = self._get_platform_asset(update_info['assets'])
            if not asset:
                raise Exception("没有找到适合当前平台的更新文件")
            
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, asset['name'])
            
            # 下载文件
            response = requests.get(asset['download_url'], stream=True, timeout=30)
            response.raise_for_status()
            
            self.download_total = int(response.headers.get('content-length', 0))
            self.download_progress = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        self.download_progress += len(chunk)
                        
                        if progress_callback:
                            progress_callback(self.download_progress, self.download_total)
                        
                        self._notify_callbacks('download_progress', {
                            'current': self.download_progress,
                            'total': self.download_total,
                            'percent': (self.download_progress / self.download_total * 100) 
                                      if self.download_total > 0 else 0
                        })
            
            self._notify_callbacks('download_complete', file_path)
            return file_path
            
        except Exception as e:
            self._notify_callbacks('download_error', str(e))
            print(f"下载更新失败: {e}")
            return None
        finally:
            self.is_downloading = False
    
    def install_update(self, update_file: str, restart: bool = True) -> bool:
        """
        安装更新
        
        Args:
            update_file: 更新文件路径
            restart: 是否重启应用
            
        Returns:
            是否安装成功
        """
        try:
            self._notify_callbacks('install_start', update_file)
            
            # 根据文件类型处理
            if update_file.endswith('.exe'):
                # Windows可执行文件
                self._install_windows_exe(update_file, restart)
            elif update_file.endswith('.zip'):
                # ZIP压缩包
                self._install_from_zip(update_file, restart)
            else:
                raise Exception(f"不支持的更新文件类型: {update_file}")
            
            self._notify_callbacks('install_complete', None)
            return True
            
        except Exception as e:
            self._notify_callbacks('install_error', str(e))
            print(f"安装更新失败: {e}")
            return False
    
    def _install_windows_exe(self, exe_path: str, restart: bool):
        """安装Windows可执行文件"""
        # 创建批处理脚本来替换文件
        batch_script = f"""
@echo off
timeout /t 2 /nobreak > nul
move /y "{exe_path}" "{sys.executable}"
if %errorlevel% == 0 (
    if "{restart}" == "True" (
        start "" "{sys.executable}"
    )
)
del "%~f0"
"""
        
        batch_file = os.path.join(tempfile.gettempdir(), 'update.bat')
        with open(batch_file, 'w') as f:
            f.write(batch_script)
        
        # 执行批处理脚本
        subprocess.Popen(batch_file, shell=True)
        
        # 退出当前程序
        sys.exit(0)
    
    def _install_from_zip(self, zip_path: str, restart: bool):
        """从ZIP文件安装更新"""
        # 解压到临时目录
        temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
        os.makedirs(temp_extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
        
        # 获取当前程序目录
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        # 创建更新脚本
        if sys.platform == 'win32':
            self._create_windows_update_script(temp_extract_dir, app_dir, restart)
        else:
            self._create_unix_update_script(temp_extract_dir, app_dir, restart)
    
    def _create_windows_update_script(self, source_dir: str, target_dir: str, restart: bool):
        """创建Windows更新脚本"""
        script = f"""
@echo off
timeout /t 2 /nobreak > nul
xcopy /s /e /y "{source_dir}\\*" "{target_dir}\\"
if %errorlevel% == 0 (
    rmdir /s /q "{source_dir}"
    if "{restart}" == "True" (
        cd "{target_dir}"
        start "" "{os.path.basename(sys.executable)}"
    )
)
del "%~f0"
"""
        
        script_file = os.path.join(tempfile.gettempdir(), 'update.bat')
        with open(script_file, 'w') as f:
            f.write(script)
        
        subprocess.Popen(script_file, shell=True)
        sys.exit(0)
    
    def _create_unix_update_script(self, source_dir: str, target_dir: str, restart: bool):
        """创建Unix更新脚本"""
        script = f"""#!/bin/bash
sleep 2
cp -rf "{source_dir}"/* "{target_dir}/"
if [ $? -eq 0 ]; then
    rm -rf "{source_dir}"
    if [ "{restart}" = "True" ]; then
        cd "{target_dir}"
        ./{os.path.basename(sys.executable)} &
    fi
fi
rm -f "$0"
"""
        
        script_file = os.path.join(tempfile.gettempdir(), 'update.sh')
        with open(script_file, 'w') as f:
            f.write(script)
        
        os.chmod(script_file, 0o755)
        subprocess.Popen(['/bin/bash', script_file])
        sys.exit(0)


def get_current_version() -> str:
    """
    获取当前版本号
    
    Returns:
        版本号字符串
    """
    # 尝试从version.py文件读取
    version_file = os.path.join(os.path.dirname(__file__), 'version.py')
    if os.path.exists(version_file):
        with open(version_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    return line.split('=')[1].strip().strip('"\'')
    
    # 默认版本号
    return "1.0.0"


def check_and_notify_update(updater: AutoUpdater, callback: Optional[Callable] = None):
    """
    后台检查更新并通知
    
    Args:
        updater: 更新器实例
        callback: 通知回调函数
    """
    def check():
        update_info = updater.check_for_updates()
        if update_info and callback:
            callback(update_info)
    
    thread = threading.Thread(target=check, daemon=True)
    thread.start()


if __name__ == "__main__":
    # 测试代码
    updater = AutoUpdater("owner/repo", "1.0.0")
    update_info = updater.check_for_updates()
    if update_info:
        print(f"发现新版本: {update_info['version']}")
        print(f"更新内容: {update_info['body']}")