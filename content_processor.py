# -*- coding: utf-8 -*-
"""
内容处理模块
负责章节内容的解析、处理和格式化
"""

import re
import json
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
try:
    from config import Config
    from network import NetworkManager
except ImportError:
    # 提供基本配置作为后备
    class Config:
        pass
    
    class NetworkManager:
        def __init__(self):
            pass
        
        def get_headers(self):
            return {}
        
        def make_request(self, *args, **kwargs):
            return None


class ContentProcessor:
    """内容处理器"""
    
    def __init__(self, network_manager: NetworkManager):
        self.network_manager = network_manager
        self.config = Config()
    
    def extract_chapters(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """从HTML中提取章节信息"""
        chapters = []
        for idx, item in enumerate(soup.select('div.chapter-item')):
            a_tag = item.find('a')
            if not a_tag:
                continue
            
            raw_title = a_tag.get_text(strip=True)
            
            if re.match(r'^(番外|特别篇|if线)\s*', raw_title):
                final_title = raw_title
            else:
                clean_title = re.sub(
                    r'^第[一二三四五六七八九十百千\d]+章\s*',
                    '', 
                    raw_title
                ).strip()
                final_title = f"第{idx+1}章 {clean_title}"
            
            chapters.append({
                "id": a_tag['href'].split('/')[-1],
                "title": final_title,
                "url": f"https://fanqienovel.com{a_tag['href']}",
                "index": idx
            })
        return chapters
    
    def _is_chapter_link(self, href: str, title: str) -> bool:
        """判断是否为章节链接"""
        # 检查URL模式
        chapter_patterns = [
            r'/chapter/',
            r'/read/',
            r'chapter_id=',
            r'chapterId='
        ]
        
        for pattern in chapter_patterns:
            if re.search(pattern, href, re.IGNORECASE):
                return True
        
        # 检查标题模式
        title_patterns = [
            r'第\s*\d+\s*章',
            r'chapter\s*\d+',
            r'第\s*[一二三四五六七八九十百千万]+\s*章'
        ]
        
        for pattern in title_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_chapter_id(self, href: str) -> Optional[str]:
        """从URL中提取章节ID"""
        # 尝试不同的ID提取模式
        patterns = [
            r'chapter_id=(\d+)',
            r'chapterId=(\d+)',
            r'/chapter/(\d+)',
            r'/read/(\d+)',
            r'id=(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, href)
            if match:
                return match.group(1)
        
        return None
    
    def process_chapter_content(self, content: str) -> str:
        """处理章节内容，清理和格式化"""
        if not content or not isinstance(content, str):
            return ""
        
        try:
            paragraphs = []
            if '<p idx=' in content:
                paragraphs = re.findall(r'<p idx="\d+">(.*?)</p>', content, re.DOTALL)
            else:
                paragraphs = content.split('\n')
            
            if paragraphs:
                first_para = paragraphs[0].strip()
                if not first_para.startswith('    '):
                    paragraphs[0] = '    ' + first_para
            
            cleaned_content = "\n".join(p.strip() for p in paragraphs if p.strip())
            formatted_content = '\n'.join('    ' + line if line.strip() else line 
                                        for line in cleaned_content.split('\n'))
            
            formatted_content = re.sub(r'<header>.*?</header>', '', formatted_content, flags=re.DOTALL)
            formatted_content = re.sub(r'<footer>.*?</footer>', '', formatted_content, flags=re.DOTALL)
            formatted_content = re.sub(r'</?article>', '', formatted_content)
            formatted_content = re.sub(r'<[^>]+>', '', formatted_content)
            formatted_content = re.sub(r'\\u003c|\\u003e', '', formatted_content)
            
            # 压缩多余的空行
            formatted_content = re.sub(r'\n{3,}', '\n\n', formatted_content).strip()
            return formatted_content
        except Exception as e:
            print(f"内容处理错误: {str(e)}")
            return str(content)
    
    def _clean_text(self, text: str) -> str:
        """清理文本内容"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符和广告文本
        unwanted_patterns = [
            r'本章未完.*?点击下一页继续阅读',
            r'请收藏本站：.*?手机版阅读网址：',
            r'一秒记住.*?为您提供精彩小说阅读',
            r'天才一秒记住.*?地址：',
            r'笔趣阁.*?最快更新',
            r'www\.[^。]*?\.com',
            r'http[s]?://[^\s]*',
            r'【.*?】',
            r'（.*?广告.*?）',
            r'\(.*?广告.*?\)',
        ]
        
        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # 移除多余的标点符号
        text = re.sub(r'[。]{2,}', '。', text)
        text = re.sub(r'[，]{2,}', '，', text)
        text = re.sub(r'[！]{2,}', '！', text)
        text = re.sub(r'[？]{2,}', '？', text)
        
        return text.strip()
    
    def _format_paragraphs(self, text: str) -> str:
        """格式化段落"""
        # 按句号分割并重新组织段落
        sentences = re.split(r'[。！？]', text)
        paragraphs = []
        current_paragraph = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            current_paragraph.append(sentence)
            
            # 每3-5句组成一个段落
            if len(current_paragraph) >= 3:
                paragraphs.append('。'.join(current_paragraph) + '。')
                current_paragraph = []
        
        # 处理剩余的句子
        if current_paragraph:
            paragraphs.append('。'.join(current_paragraph) + '。')
        
        return '\n\n'.join(paragraphs)
    
    
    def extract_book_info_from_html(self, html_content: str) -> Dict[str, Any]:
        """从HTML中提取书籍信息"""
        soup = BeautifulSoup(html_content, 'html.parser')
        book_info = {}
        
        # 提取标题
        title_selectors = [
            'h1',
            '.book-title',
            '.title',
            '[class*="title"]',
            'title'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                book_info['title'] = title_elem.get_text(strip=True)
                break
        
        # 提取作者
        author_selectors = [
            '.author',
            '[class*="author"]',
            '.writer',
            '[class*="writer"]'
        ]
        
        for selector in author_selectors:
            author_elem = soup.select_one(selector)
            if author_elem:
                book_info['author'] = author_elem.get_text(strip=True)
                break
        
        # 提取简介
        intro_selectors = [
            '.intro',
            '.introduction',
            '.summary',
            '[class*="intro"]',
            '[class*="summary"]'
        ]
        
        for selector in intro_selectors:
            intro_elem = soup.select_one(selector)
            if intro_elem:
                book_info['introduction'] = intro_elem.get_text(strip=True)
                break
        
        # 提取封面
        cover_selectors = [
            'img[class*="cover"]',
            '.cover img',
            '.book-cover img',
            'img[alt*="封面"]'
        ]
        
        for selector in cover_selectors:
            cover_elem = soup.select_one(selector)
            if cover_elem:
                book_info['cover_url'] = cover_elem.get('src', '')
                break
        
        return book_info
    
    def batch_download_chapters(self, item_ids, headers):
        """批量下载章节内容"""
        from config import CONFIG
        
        if not CONFIG["batch_config"]["enabled"] or CONFIG["batch_config"]["name"] != "qyuing":
            print("批量下载功能仅限qyuing API")
            return None
            
        batch_config = CONFIG["batch_config"]
        url = f"{batch_config['base_url']}{batch_config['batch_endpoint']}"
        
        try:
            batch_headers = headers.copy()
            if batch_config["token"]:
                batch_headers["token"] = batch_config["token"]
            batch_headers["Content-Type"] = "application/json"
            
            payload = {"item_ids": item_ids}
            response = self.network_manager.make_request(
                url,
                headers=batch_headers,
                method='POST',
                data=payload,
                timeout=batch_config["timeout"],
                verify=False
            )
            
            if response and response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "data" in data:
                    return data["data"]
                return data
            else:
                if response:
                    print(f"批量下载失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            print(f"批量下载异常: {str(e)}")
            return None