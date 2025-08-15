# -*- coding: utf-8 -*-
"""
网络请求模块
统一处理HTTP请求、请求头生成和API端点管理
"""

import requests
import random
import time
import json
import os
import urllib3
from typing import Dict, List, Optional, Any
from fake_useragent import UserAgent
from config import Config

# 禁用SSL证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()


class NetworkManager:
    """网络请求管理器"""
    
    # 备用用户代理列表
    FALLBACK_USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    def __init__(self):
        self.config = Config()
        
        # 尝试初始化UserAgent，失败时使用备用方案
        try:
            self.ua = UserAgent()
            self.use_fake_useragent = True
            print("成功初始化fake_useragent")
        except Exception as e:
            print(f"fake_useragent初始化失败: {e}")
            print("使用备用用户代理列表")
            self.ua = None
            self.use_fake_useragent = False
            
        self.session = requests.Session()
        
    def get_random_user_agent(self) -> str:
        """获取随机用户代理"""
        if self.use_fake_useragent and self.ua:
            try:
                return self.ua.random
            except Exception as e:
                print(f"获取用户代理失败，切换到备用方案: {e}")
                self.use_fake_useragent = False
                
        # 使用备用用户代理
        return random.choice(self.FALLBACK_USER_AGENTS)
        
    def get_headers(self) -> Dict[str, str]:
        """生成随机请求头"""
        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Connection': 'keep-alive',
            'Referer': 'https://fanqienovel.com/'
        }
        return headers
    
    def make_request(self, url: str, headers: Optional[Dict[str, str]] = None, 
                    params: Optional[Dict[str, Any]] = None, 
                    data: Optional[Any] = None, 
                    method: str = 'GET', 
                    timeout: Optional[int] = None,
                    verify: bool = True) -> Optional[requests.Response]:
        """
        统一的HTTP请求方法
        
        Args:
            url: 请求URL
            headers: 请求头
            params: URL参数
            data: POST数据（可为dict或JSON字符串）
            method: 请求方法
            timeout: 超时时间
            
        Returns:
            Response对象或None
        """
        if headers is None:
            headers = self.get_headers()
            
        if timeout is None:
            timeout = self.config.REQUEST_TIMEOUT
            
        for attempt in range(self.config.MAX_RETRIES):
            try:
                request_params = {
                    'headers': headers,
                    'params': params,
                    'timeout': timeout,
                    'verify': verify
                }
                
                if method.upper() == 'GET':
                    response = self.session.get(url, **request_params)
                elif method.upper() == 'POST':
                    # Handle JSON data
                    if data and isinstance(data, dict):
                        request_params['json'] = data
                    else:
                        request_params['data'] = data
                    response = self.session.post(url, **request_params)
                else:
                    if data and isinstance(data, dict):
                        request_params['json'] = data
                    else:
                        request_params['data'] = data
                    response = self.session.request(method, url, **request_params)
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                print(f"请求失败 (尝试 {attempt + 1}/{self.config.MAX_RETRIES}): {e}")
                if attempt < self.config.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    print(f"请求最终失败: {url}")
                    return None
                    
        return None
    
    def _get_server_base(self) -> str:
        """从SERVER_URL推导基础域名（不含具体路径）"""
        return self.config.SERVER_URL.rstrip('/')
    
    def fetch_api_endpoints_from_server(self, gui_callback=None) -> List[Dict[str, Any]]:
        """从服务器获取API端点列表（包含人机验证流程），并填充到Config中
        
        Args:
            gui_callback: GUI回调函数，用于处理验证码输入
        """
        try:
            headers = self.get_headers()
            headers.update({
                'X-Auth-Token': self.config.AUTH_TOKEN,
                'Content-Type': 'application/json'
            })
            
            # 直接尝试获取sources（如果服务器未强制验证）
            sources_url = f"{self.config.SERVER_URL}/api/sources"
            response = self.make_request(sources_url, headers=headers, timeout=10, verify=False)
            
            if not response or response.status_code != 200:
                # 触发人机验证流程
                base = self._get_server_base()
                challenge_url = f"{base}/api/get-captcha-challenge"
                print("Fetching captcha challenge...")
                challenge_res = self.make_request(challenge_url, headers=headers, timeout=10, verify=False)
                if challenge_res and challenge_res.status_code == 200:
                    challenge_data = challenge_res.json()
                    captcha_url = challenge_data.get("challenge_url")
                    if captcha_url:
                        # 修复缺少端口号的问题
                        if "dlbkltos.s7123.xyz" in captcha_url and ":5080" not in captcha_url:
                            # 在域名后添加端口号
                            captcha_url = captcha_url.replace("dlbkltos.s7123.xyz", "dlbkltos.s7123.xyz:5080")
                        # 支持环境变量以便GUI/非交互环境
                        verification_token = os.environ.get("TOMATO_VERIFICATION_TOKEN")
                        
                        # 如果没有环境变量且有GUI回调，使用GUI处理
                        if not verification_token and gui_callback:
                            verification_token = gui_callback(captcha_url)
                        # 如果没有GUI回调且没有环境变量，尝试终端输入（仅在有终端时）
                        elif not verification_token and not gui_callback:
                            try:
                                # 检查是否有终端（避免exe模式下崩溃）
                                import sys
                                if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
                                    print("\n==================================================")
                                    print("Human verification required")
                                    print("Please open this link in browser:")
                                    print(captcha_url)
                                    print("Complete verification and paste the token")
                                    print("==================================================\n")
                                    verification_token = input("Paste verification token: ").strip()
                                else:
                                    print("No terminal available for input. Please set TOMATO_VERIFICATION_TOKEN environment variable.")
                                    verification_token = ""
                            except Exception:
                                verification_token = ""
                        
                        if verification_token:
                            headers["X-Verification-Token"] = verification_token
                            response = self.make_request(sources_url, headers=headers, timeout=10, verify=False)
                        else:
                            print("No verification token provided, cannot fetch API list from server.")
                            # 返回空列表而不是继续尝试，让程序使用默认API
                            return []
                else:
                    print(f"Failed to get captcha challenge: {challenge_res.status_code if challenge_res else 'None'}")
            
            api_endpoints: List[Dict[str, Any]] = []
            
            if response and response.status_code == 200:
                try:
                    data = response.json()
                    sources = data.get("sources", []) if isinstance(data, dict) else []
                    
                    # 重置
                    Config.update_api_endpoints([])
                    
                    for source in sources:
                        try:
                            if not source.get("enabled"):
                                continue
                            name = source.get("name", "")
                            single_url = source.get("single_url", "")
                            if not single_url:
                                continue
                            
                            # 处理批量配置 (qyuing API)
                            if name == "qyuing":
                                base_url = single_url.split('?')[0]
                                batch_endpoint = base_url.split('/')[-1]
                                base_url = base_url.rsplit('/', 1)[0]
                                
                                from config import CONFIG
                                CONFIG["batch_config"]["base_url"] = base_url
                                CONFIG["batch_config"]["batch_endpoint"] = f"/{batch_endpoint}"
                                CONFIG["batch_config"]["token"] = source.get("token", "")
                                CONFIG["batch_config"]["enabled"] = True
                            
                            endpoint: Dict[str, Any] = {"url": single_url, "name": name}
                            
                            # fanqie_sdk特殊处理
                            if name == "fanqie_sdk":
                                endpoint["params"] = source.get("params", {})
                                endpoint["data"] = source.get("data", {})
                            
                            api_endpoints.append(endpoint)
                        except Exception as e:
                            print(f"解析source失败: {e}")
                    
                    # 更新全局配置
                    Config.update_api_endpoints(api_endpoints)
                    
                    print("成功从服务器获取API列表!")
                    return api_endpoints
                except json.JSONDecodeError:
                    print("服务器返回非JSON响应")
            else:
                print(f"服务器响应异常: {response.status_code if response else 'None'}")
                
        except Exception as e:
            print(f"获取API端点时发生错误: {e}")
            
        # 返回空列表，让主程序处理
        print("使用默认API端点(为空)")
        return []
    
    def get_api_endpoints(self) -> List[Dict[str, Any]]:
        """获取API端点列表（优先从服务器获取，失败则使用默认）"""
        if not self.config.API_ENDPOINTS:
            self.config.API_ENDPOINTS = self.fetch_api_endpoints_from_server()
        return self.config.API_ENDPOINTS
    
    def test_endpoint(self, endpoint: str) -> bool:
        """测试API端点是否可用"""
        try:
            response = self.make_request(endpoint, timeout=5)
            return response is not None and response.status_code == 200
        except:
            return False
    
    def get_working_endpoints(self) -> List[str]:
        """获取可用的API端点"""
        endpoints = self.get_api_endpoints()
        working_endpoints = []
        
        for endpoint in endpoints:
            url = endpoint["url"] if isinstance(endpoint, dict) else endpoint
            if self.test_endpoint(url):
                working_endpoints.append(url)
                
        return working_endpoints if working_endpoints else [e["url"] if isinstance(e, dict) else e for e in endpoints]
    
    def close(self):
        """关闭会话"""
        if self.session:
            self.session.close()