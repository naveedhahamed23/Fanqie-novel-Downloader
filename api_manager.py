#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API管理模块 - 负责API的保存、加载和用户选择
"""

import os
import json
import time
from typing import Dict, List, Optional
from config import CONFIG, print_lock

class APIManager:
    """API管理器"""
    
    def __init__(self):
        self.api_file = "saved_apis.json"
        self.last_update_file = "api_last_update.json"
    
    def save_apis(self, api_endpoints: List[Dict], batch_config: Dict):
        """保存API到本地文件"""
        try:
            api_data = {
                "timestamp": time.time(),
                "api_endpoints": api_endpoints,
                "batch_config": batch_config
            }
            
            with open(self.api_file, 'w', encoding='utf-8') as f:
                json.dump(api_data, f, ensure_ascii=False, indent=2)
            
            # 保存最后更新时间
            update_info = {
                "last_update": time.time(),
                "api_count": len(api_endpoints),
                "batch_enabled": batch_config.get("enabled", False)
            }
            
            with open(self.last_update_file, 'w', encoding='utf-8') as f:
                json.dump(update_info, f, ensure_ascii=False, indent=2)
            
            with print_lock:
                print(f"API配置已保存到: {self.api_file}")
            
            return True
        except Exception as e:
            with print_lock:
                print(f"保存API配置失败: {str(e)}")
            return False
    
    def load_apis(self) -> Optional[Dict]:
        """从本地文件加载API"""
        try:
            if not os.path.exists(self.api_file):
                return None
            
            with open(self.api_file, 'r', encoding='utf-8') as f:
                api_data = json.load(f)
            
            # 验证数据完整性
            if not isinstance(api_data, dict):
                return None
            
            required_keys = ["timestamp", "api_endpoints", "batch_config"]
            if not all(key in api_data for key in required_keys):
                return None
            
            # 检查API是否过期（7天）
            current_time = time.time()
            if current_time - api_data["timestamp"] > 7 * 24 * 3600:
                with print_lock:
                    print("保存的API已过期（超过7天），需要重新获取")
                return None
            
            with print_lock:
                print(f"从本地加载API配置: {self.api_file}")
                print(f"API数量: {len(api_data['api_endpoints'])}")
                print(f"批量下载: {'启用' if api_data['batch_config'].get('enabled') else '禁用'}")
            
            return api_data
        except Exception as e:
            with print_lock:
                print(f"加载API配置失败: {str(e)}")
            return None
    
    def get_last_update_info(self) -> Optional[Dict]:
        """获取最后更新信息"""
        try:
            if not os.path.exists(self.last_update_file):
                return None
            
            with open(self.last_update_file, 'r', encoding='utf-8') as f:
                update_info = json.load(f)
            
            return update_info
        except Exception:
            return None
    
    def format_update_time(self, timestamp: float) -> str:
        """格式化更新时间"""
        import datetime
        update_time = datetime.datetime.fromtimestamp(timestamp)
        now = datetime.datetime.now()
        diff = now - update_time
        
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}小时前"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    
    def apply_saved_apis(self, api_data: Dict):
        """应用保存的API配置到全局CONFIG"""
        try:
            # 更新API端点
            CONFIG["api_endpoints"] = api_data["api_endpoints"]
            
            # 更新批量配置
            batch_config = api_data["batch_config"]
            CONFIG["batch_config"].update(batch_config)
            
            with print_lock:
                print("已应用保存的API配置")
            
            return True
        except Exception as e:
            with print_lock:
                print(f"应用API配置失败: {str(e)}")
            return False
    
    def clear_saved_apis(self):
        """清除保存的API配置"""
        try:
            if os.path.exists(self.api_file):
                os.remove(self.api_file)
            if os.path.exists(self.last_update_file):
                os.remove(self.last_update_file)
            
            with print_lock:
                print("已清除保存的API配置")
            
            return True
        except Exception as e:
            with print_lock:
                print(f"清除API配置失败: {str(e)}")
            return False

# 全局API管理器实例
api_manager = APIManager()
