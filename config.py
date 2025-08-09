# -*- coding: utf-8 -*-
"""
配置管理模块
统一管理所有配置信息，避免重复定义
"""

class Config:
    """应用程序配置类"""
    
    # 基础配置
    MAX_WORKERS = 4
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 15
    STATUS_FILE = "chapter.json"
    REQUEST_RATE_LIMIT = 0.4
    
    # 认证配置
    AUTH_TOKEN = "wcnmd91jb"
    SERVER_URL = "https://dlbkltos.s7123.xyz:5080"
    
    # API端点配置
    API_ENDPOINTS = []
    
    # 批量下载配置
    BATCH_CONFIG = {
        "name": "qyuing",
        "base_url": None,
        "batch_endpoint": None,
        "token": None,
        "max_batch_size": 290,
        "timeout": 10,
        "enabled": False
    }
    
    # 用户代理配置
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    
    # 文件输出配置
    OUTPUT_CONFIG = {
        "txt_encoding": "utf-8",
        "epub_encoding": "utf-8",
        "default_format": "txt",
        "create_subdirs": True
    }
    
    # 网络请求配置
    NETWORK_CONFIG = {
        "verify_ssl": True,
        "allow_redirects": True,
        "stream": False,
        "connection_pool_size": 10
    }
    
    @classmethod
    def get_config_dict(cls):
        """获取完整配置字典（兼容旧代码）"""
        return {
            "max_workers": cls.MAX_WORKERS,
            "max_retries": cls.MAX_RETRIES,
            "request_timeout": cls.REQUEST_TIMEOUT,
            "status_file": cls.STATUS_FILE,
            "request_rate_limit": cls.REQUEST_RATE_LIMIT,
            "auth_token": cls.AUTH_TOKEN,
            "server_url": cls.SERVER_URL,
            "api_endpoints": cls.API_ENDPOINTS,
            "batch_config": cls.BATCH_CONFIG
        }
    
    @classmethod
    def update_api_endpoints(cls, endpoints):
        """更新API端点列表"""
        cls.API_ENDPOINTS = endpoints
    

# 为了兼容旧代码，提供动态CONFIG变量
class ConfigDict(dict):
    """Dynamic config dict that always reflects current Config values"""
    def __getitem__(self, key):
        if key == "api_endpoints":
            return Config.API_ENDPOINTS
        elif key == "batch_config":
            return Config.BATCH_CONFIG
        else:
            return Config.get_config_dict()[key]
    
    def __setitem__(self, key, value):
        if key == "api_endpoints":
            Config.API_ENDPOINTS = value
        elif key == "batch_config":
            Config.BATCH_CONFIG = value
        else:
            # Update the Config class attribute if it exists
            attr_name = key.upper()
            if hasattr(Config, attr_name):
                setattr(Config, attr_name, value)
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

CONFIG = ConfigDict()

# 导出主要的配置对象
__all__ = ['Config', 'CONFIG']