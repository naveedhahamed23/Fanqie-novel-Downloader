#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
番茄小说API调用脚本 - 重构版
使用模块化组件，支持GUI进度回调
"""

import time
import threading
import signal
import sys
import tempfile
from typing import Optional, Callable

# 导入新的模块化组件
from config import CONFIG
from network import NetworkManager
from content_processor import ContentProcessor
from download_engine import DownloadEngine
from file_output import FileOutputManager
from state_manager import StateManager

# 全局锁
print_lock = threading.Lock()


class EnhancedNovelDownloader:
    """增强型小说下载器 - 使用模块化组件"""
    
    def __init__(self):
        self.progress_callback = None
        self.is_cancelled = False
        self.chapter_results = {}
        
        # 初始化模块化组件
        self.network_manager = NetworkManager()
        self.content_processor = ContentProcessor(self.network_manager)
        self.download_engine = DownloadEngine(self.network_manager, self.content_processor)
        self.file_output_manager = FileOutputManager()
        self.state_manager = StateManager()
        
    def cancel_download(self):
        """取消下载"""
        self.is_cancelled = True
        
    def run_download(self, book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, gui_callback=None):
        """运行下载"""
        try:
            # 在开始下载时进行API端点验证
            if not CONFIG["api_endpoints"]:
                if self.progress_callback:
                    self.progress_callback(5, "正在验证下载接口...")
                self.network_manager.fetch_api_endpoints_from_server(gui_callback)
            
            headers = self.network_manager.get_headers()
            chapters = self.download_engine.get_chapters_from_api(book_id, headers)
            if not chapters:
                raise Exception("未找到任何章节，请检查小说ID是否正确。")
            
            name, author_name, description = self.download_engine.get_book_info(book_id, headers)
            if not name:
                name = f"未知小说_{book_id}"
                author_name = "未知作者"
                description = "无简介"

            # 获取增强信息（用于封面等）
            enhanced_info = None
            try:
                enhanced_info = self.download_engine.get_book_info_enhanced(book_id, headers)
            except Exception:
                enhanced_info = None

            # 确定下载范围
            if start_chapter is not None and end_chapter is not None:
                chapters = chapters[start_chapter:end_chapter+1]
                output_filename = f"{name}_第{start_chapter+1}-{end_chapter+1}章.{file_format}"
            else:
                output_filename = f"{name}.{file_format}"

            downloaded = self.state_manager.load_status(save_path)
            todo_chapters = [ch for ch in chapters if ch["id"] not in downloaded]
            
            if self.progress_callback:
                self.progress_callback(5, f"开始下载：《{name}》, 总章节数: {len(chapters)}, 待下载: {len(todo_chapters)}")

            import os
            os.makedirs(save_path, exist_ok=True)
            output_file_path = os.path.join(save_path, output_filename)
            
            success_count = 0
            failed_chapters = []
            self.chapter_results = {}
            lock = threading.Lock()

            # 批量下载模式
            if CONFIG["batch_config"]["enabled"] and CONFIG["batch_config"]["name"] == "qyuing":
                if self.progress_callback:
                    self.progress_callback(10, "启用qyuing API批量下载模式...")
                    
                batch_size = CONFIG["batch_config"]["max_batch_size"]
                
                for i in range(0, len(todo_chapters), batch_size):
                    if self.is_cancelled:
                        break
                        
                    batch = todo_chapters[i:i + batch_size]
                    item_ids = [chap["id"] for chap in batch]
                    
                    if self.progress_callback:
                        progress = 10 + (i / len(todo_chapters)) * 60
                        self.progress_callback(progress, f"批量下载第 {i//batch_size + 1} 批...")
                    
                    batch_results = self.content_processor.batch_download_chapters(item_ids, headers)
                    if not batch_results:
                        failed_chapters.extend(batch)
                        continue
                    
                    for chap in batch:
                        content = batch_results.get(chap["id"], "")
                        if isinstance(content, dict):
                            content = content.get("content", "")
                        
                        if content:
                            processed = self.content_processor.process_chapter_content(content)
                            with lock:
                                self.chapter_results[chap["index"]] = {
                                    "base_title": chap["title"],
                                    "api_title": "",
                                    "content": processed
                                }
                                downloaded.add(chap["id"])
                                success_count += 1
                        else:
                            with lock:
                                failed_chapters.append(chap)
                
                todo_chapters = failed_chapters.copy()
                failed_chapters = []
                self.state_manager.save_status(save_path, downloaded)

            # 单章下载模式（处理剩余章节）
            if todo_chapters and not self.is_cancelled:
                if self.progress_callback:
                    self.progress_callback(70, f"开始单章下载模式，剩余 {len(todo_chapters)} 个章节...")
                
                def download_task(chapter):
                    nonlocal success_count
                    try:
                        if self.is_cancelled:
                            return
                            
                        title, content = self.download_engine.down_text(chapter["id"], headers, book_id)
                        if content:
                            with lock:
                                self.chapter_results[chapter["index"]] = {
                                    "base_title": chapter["title"],
                                    "api_title": title,
                                    "content": content
                                }
                                downloaded.add(chapter["id"])
                                success_count += 1
                        else:
                            with lock:
                                failed_chapters.append(chapter)
                    except Exception as e:
                        with lock:
                            failed_chapters.append(chapter)

                # 使用线程池下载
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
                    futures = [executor.submit(download_task, ch) for ch in todo_chapters]
                    
                    completed_count = 0
                    for future in as_completed(futures):
                        if self.is_cancelled:
                            break
                        completed_count += 1
                        if self.progress_callback:
                            progress = 70 + (completed_count / len(todo_chapters)) * 25
                            self.progress_callback(progress, f"单章下载进度: {completed_count}/{len(todo_chapters)}")
                
                self.state_manager.save_status(save_path, downloaded)

            # 保存文件
            if not self.is_cancelled and self.chapter_results:
                if self.progress_callback:
                    self.progress_callback(95, "正在保存文件...")
                
                # 组装附加书籍信息（封面等）
                extra_book_data = {}
                if enhanced_info:
                    for key in ("thumb_url", "expand_thumb_url", "audio_thumb_url_hd", "source"):
                        if key in enhanced_info:
                            extra_book_data[key] = enhanced_info.get(key)
                
                self._write_downloaded_chapters_in_order(
                    output_file_path, name, author_name, description, file_format, chapters, extra_book_data
                )
                
                if self.progress_callback:
                    self.progress_callback(100, f"下载完成！成功下载 {success_count} 个章节")

        except Exception as e:
            if self.progress_callback:
                self.progress_callback(-1, f"下载错误: {str(e)}")
            raise e
    
    def _write_downloaded_chapters_in_order(self, output_file_path, name, author_name, description, file_format, chapters, extra_book_data=None):
        """按章节顺序写入文件"""
        if not self.chapter_results:
            return
            
        book_data = {
            'name': name,
            'author': author_name,
            'description': description
        }
        if extra_book_data:
            book_data.update(extra_book_data)
        
        if file_format == 'txt':
            self.file_output_manager.save_as_txt(output_file_path, book_data, chapters, self.chapter_results)
        elif file_format == 'epub':
            self.file_output_manager.save_as_epub(output_file_path, book_data, chapters, self.chapter_results)
            
        # 下载完成后自动清理chapter.json
        try:
            import os
            status_file = os.path.join(os.path.dirname(output_file_path), CONFIG["status_file"])
            if os.path.exists(status_file):
                os.remove(status_file)
        except Exception as e:
            print(f"自动清理chapter.json失败: {e}")


class TomatoNovelAPI:
    """番茄小说API类 - 集成增强型下载器"""
    
    def __init__(self, gui_callback=None):
        """初始化API，集成增强型下载器
        
        Args:
            gui_callback: GUI验证码回调函数
        """
        # 初始化增强型下载器
        self.enhanced_downloader = EnhancedNovelDownloader()
        
        # 下载状态
        self.current_progress_callback = None
        self.gui_verification_callback = gui_callback
        
        # 初始化模块化组件
        self.network_manager = NetworkManager()
        self.content_processor = ContentProcessor(self.network_manager)
        self.download_engine = DownloadEngine(self.network_manager, self.content_processor)
        self.file_output_manager = FileOutputManager()
        self.state_manager = StateManager()
        
        # 不在初始化时获取API端点，延迟到下载时
    
    def search_novels(self, keyword, offset=0, tab_type=1):
        """
        使用fqweb.jsj66.com的API进行搜索，适配真实返回结构，返回与原来兼容的数据结构。
        """
        try:
            url = "http://fqweb.jsj66.com/search"
            params = {
                "query": keyword,
                "page": offset // 10 + 1  # 页码从1开始
            }
            resp = self.network_manager.make_request(url, params=params, timeout=10)
            
            # 检查响应状态
            if resp.status_code != 200:
                print(f"fqweb API返回错误状态: {resp.status_code}")
                raise Exception(f"HTTP {resp.status_code}")
            
            # 安全解析JSON
            try:
                data = resp.json()
            except Exception as json_err:
                print(f"fqweb API响应不是有效JSON: {json_err}")
                print(f"响应内容: {resp.text[:200]}...")
                raise Exception("无效的JSON响应")
            
            # 检查数据类型
            if not isinstance(data, dict):
                print(f"fqweb API返回了非字典类型: {type(data)}")
                print(f"返回内容: {str(data)[:200]}...")
                raise Exception("API返回格式错误")
            
            items = []
            # 适配真实结构
            if (
                data.get("data")
                and isinstance(data["data"], dict)
                and data["data"].get("code") in ("0", 0)
                and data["data"].get("search_tabs")
                and isinstance(data["data"]["search_tabs"], list)
            ):
                for tab in data["data"]["search_tabs"]:
                    if not isinstance(tab, dict):
                        continue
                    for entry in tab.get("data", []):
                        if not isinstance(entry, dict):
                            continue
                        for book in entry.get("book_data", []):
                            if not isinstance(book, dict):
                                continue
                            items.append({
                                "book_id": book.get("book_id", book.get("id", "")),
                                "book_name": book.get("book_name", book.get("name", "")),
                                "author": book.get("author", "未知作者"),
                                "category": book.get("category", ""),
                                "abstract": book.get("abstract", book.get("desc", "")),
                                "score": book.get("score", ""),
                                "serial_count": book.get("serial_count", ""),
                                "word_number": book.get("word_number", ""),
                                "thumb_url": book.get("thumb_url", ""),
                                "creation_status": book.get("creation_status", ""),
                                "tags": book.get("tags", ""),
                                "sub_info": book.get("sub_info", ""),
                                "tomato_book_status": book.get("tomato_book_status", ""),
                                "source": "fqweb"
                            })
            
            return {
                "success": True,
                "data": {
                    "items": items,
                    "has_more": len(items) == 10,
                    "next_offset": offset + 10,
                    "search_keyword": keyword,
                    "source": "fqweb"
                }
            }
        except Exception as e:
            print(f"fqweb搜索失败: {e}")
        return {
            "success": False,
            "data": {
                "items": [],
                "has_more": False,
                "next_offset": offset + 10,
                "search_keyword": keyword,
                "source": "fqweb"
            }
        }

    def get_novel_info(self, book_id):
        """
        获取小说信息 - 优先使用增强API
        
        Args:
            book_id (str): 小说ID
            
        Returns:
            dict: 小说信息
        """
        try:
            # 在获取小说信息时检查API端点
            if not CONFIG["api_endpoints"]:
                self.network_manager.fetch_api_endpoints_from_server(self.gui_verification_callback)
            
            headers = self.network_manager.get_headers()
            
            # 首先尝试使用增强API
            enhanced_info = self.download_engine.get_book_info_enhanced(book_id, headers)
            if enhanced_info:
                return {
                    'isSuccess': True,
                    'data': {
                        'data': enhanced_info,
                        'enhanced': True  # 标记为增强信息
                    }
                }
            
            # 增强API失败，回退到原方法
            with print_lock:
                print("增强API失败，回退到网页爬取方式")
            name, author, description = self.download_engine.get_book_info(book_id, headers)
            
            if name:
                return {
                    'isSuccess': True,
                    'data': {
                        'data': {
                            'book_name': name,
                            'author': author,
                            'abstract': description,
                            'book_id': book_id,
                            'source': '番茄小说'
                        },
                        'enhanced': False  # 标记为基础信息
                    }
                }
        except Exception as e:
            print(f"获取书籍信息失败: {e}")
        
        # 所有方法都失败
        print("所有获取书籍信息的方法都失败了")
        return {'isSuccess': False, 'errorMsg': '获取书籍信息失败'}
    
    def get_chapter_content(self, item_ids):
        """
        获取章节内容 - 使用模块化组件
        
        Args:
            item_ids (str): 章节ID
            
        Returns:
            dict: 章节内容
        """
        try:
            # 在获取章节内容时检查API端点
            if not CONFIG["api_endpoints"]:
                self.network_manager.fetch_api_endpoints_from_server(self.gui_verification_callback)
            
            headers = self.network_manager.get_headers()
            title, content = self.download_engine.down_text(item_ids, headers)
            
            if content:
                processed_content = self.content_processor.process_chapter_content(content)
                # 构造符合预期格式的返回结果
                processed_result = {
                    'isSuccess': True,
                    'data': {
                        'data': {
                            'content': processed_content,
                            'title': title,
                            'chapter_word_number': len(processed_content.replace(' ', '').replace('\n', '').replace('\t', ''))
                        }
                    }
                }
                return processed_result
        except Exception as e:
            print(f"获取章节内容失败: {e}")
            
        # API失败
        print("获取章节内容失败")
        return None
    
    def get_book_catalog(self, book_id):
        """
        获取书籍目录 - 使用模块化组件
        
        Args:
            book_id (str): 书籍ID
            
        Returns:
            dict: 目录信息
        """
        try:
            # 在获取书籍目录时检查API端点
            if not CONFIG["api_endpoints"]:
                self.network_manager.fetch_api_endpoints_from_server(self.gui_verification_callback)
            
            headers = self.network_manager.get_headers()
            chapters = self.download_engine.get_chapters_from_api(book_id, headers)
            
            if chapters:
                # 构造符合预期格式的返回结果
                processed_result = {
                    'isSuccess': True,
                    'data': {
                        'data': {
                            'item_data_list': [{'item_id': ch['id']} for ch in chapters]
                        }
                    }
                }
                return processed_result
        except Exception as e:
            print(f"获取书籍目录失败: {e}")
            
        # API失败
        print("获取书籍目录失败")
        return None

    def get_book_details(self, bookId):
        """
        获取书籍详细信息（章节列表） - 使用模块化组件
        
        Args:
            bookId (str): 书籍ID
            
        Returns:
            dict: 包含章节ID列表的书籍详细信息
        """
        try:
            # 在获取书籍详情时检查API端点
            if not CONFIG["api_endpoints"]:
                self.network_manager.fetch_api_endpoints_from_server(self.gui_verification_callback)
            
            # 使用模块化组件获取章节列表
            headers = self.network_manager.get_headers()
            chapters = self.download_engine.get_chapters_from_api(bookId, headers)
            
            if chapters:
                all_item_ids = [ch["id"] for ch in chapters]
                print(f"使用模块化组件获取到 {len(all_item_ids)} 个章节")
                return {
                    "data": {
                        "allItemIds": all_item_ids
                    },
                    "isSuccess": True
                }
        except Exception as e:
            print(f"获取章节列表失败: {e}")
        
        # API失败
        print("获取书籍详细信息失败")
        return None

    def download_full_novel(self, book_id, item_ids):
        """
        一次性下载整本小说 - 使用增强型下载器
        
        Args:
            book_id (str): 小说ID
            item_ids (list or str): 章节ID列表或逗号分隔的章节ID字符串
            
        Returns:
            dict: 小说完整内容
        """
        import tempfile
        
        # 在开始下载时进行API端点验证
        if not CONFIG["api_endpoints"]:
            if self.current_progress_callback:
                self.current_progress_callback(5, "正在验证下载接口...")
            self.network_manager.fetch_api_endpoints_from_server(self.gui_verification_callback)
        
        # 设置进度回调
        self.enhanced_downloader.progress_callback = self.current_progress_callback
        
        try:
            # 创建临时目录用于下载
            with tempfile.TemporaryDirectory() as temp_dir:
                # 确定章节范围
                if isinstance(item_ids, list):
                    item_ids_list = item_ids
                else:
                    item_ids_list = item_ids.split(',') if isinstance(item_ids, str) else []
                
                if not item_ids_list:
                    return {
                        'isSuccess': False,
                        'errorMsg': '章节ID列表为空'
                    }
                
                # 获取完整章节列表以确定范围
                headers = self.network_manager.get_headers()
                all_chapters = self.download_engine.get_chapters_from_api(book_id, headers)
                
                if not all_chapters:
                    return {
                        'isSuccess': False,
                        'errorMsg': '无法获取章节列表'
                    }
                
                # 找到要下载的章节在全部章节中的位置
                chapter_indices = []
                for item_id in item_ids_list:
                    for i, chapter in enumerate(all_chapters):
                        if chapter['id'] == item_id:
                            chapter_indices.append(i)
                            break
                
                if not chapter_indices:
                    return {
                        'isSuccess': False,
                        'errorMsg': '未找到匹配的章节'
                    }
                
                start_chapter = min(chapter_indices)
                end_chapter = max(chapter_indices)
                
                # 使用增强型下载器下载
                self.enhanced_downloader.run_download(
                    book_id, 
                    temp_dir, 
                    'txt',
                    start_chapter,
                    end_chapter,
                    self.gui_verification_callback
                )
                
                # 构建章节内容列表
                chapters_content = []
                for idx in range(start_chapter, end_chapter + 1):
                    if idx in self.enhanced_downloader.chapter_results:
                        result = self.enhanced_downloader.chapter_results[idx]
                        chapters_content.append({
                            'title': result['base_title'],
                            'content': result['content']
                        })
                
                return {
                    'isSuccess': True,
                    'data': {
                        'data': chapters_content,
                        'totalChapters': len(item_ids_list),
                        'successChapters': len(chapters_content),
                        'failedChapters': len(item_ids_list) - len(chapters_content)
                    }
                }
                
        except Exception as e:
            error_msg = str(e)
            print(f"增强型下载器错误: {error_msg}")
            
            return {
                'isSuccess': False,
                'errorMsg': f'下载失败: {error_msg}'
            }
    
    def set_progress_callback(self, callback: Optional[Callable] = None):
        """设置进度回调函数"""
        self.current_progress_callback = callback
        if self.enhanced_downloader:
            self.enhanced_downloader.progress_callback = callback
    
    def cancel_download(self):
        """取消当前下载"""
        if self.enhanced_downloader:
            self.enhanced_downloader.cancel_download()


def main():
    """主函数，用于独立运行脚本"""
    api = TomatoNovelAPI()
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  搜索小说: python tomato_novel_api.py search <关键词>")
        print("  获取小说信息: python tomato_novel_api.py novel_info <书籍ID>")
        print("  获取书籍详细信息: python tomato_novel_api.py book_details <书籍ID>")
        print("  获取书籍目录: python tomato_novel_api.py catalog <书籍ID>")
        print("  获取章节内容: python tomato_novel_api.py chapter_content <章节ID>")
        print("  下载整本小说: python tomato_novel_api.py download_full <书籍ID> <章节ID列表>")
        return
    
    command = sys.argv[1]
    
    if command == "search":
        if len(sys.argv) < 3:
            print("请提供搜索关键词")
            return
        
        keyword = sys.argv[2]
        print(f"正在搜索: {keyword}")
        result = api.search_novels(keyword)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("搜索失败")
            
    elif command == "novel_info":
        if len(sys.argv) < 3:
            print("请提供书籍ID")
            return
        
        book_id = sys.argv[2]
        print(f"正在获取书籍信息: {book_id}")
        result = api.get_novel_info(book_id)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("获取书籍信息失败")
            
    elif command == "catalog":
        if len(sys.argv) < 3:
            print("请提供书籍ID")
            return
        
        book_id = sys.argv[2]
        print(f"正在获取书籍目录: {book_id}")
        result = api.get_book_catalog(book_id)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("获取书籍目录失败")
            
    elif command == "book_details":
        if len(sys.argv) < 3:
            print("请提供书籍ID")
            return
            
        bookId = sys.argv[2]
        print(f"正在获取书籍详细信息: {bookId}")
        result = api.get_book_details(bookId)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("获取书籍详细信息失败")
            
    elif command == "chapter_content":
        if len(sys.argv) < 3:
            print("请提供章节ID")
            return
            
        item_ids = sys.argv[2]
        print(f"正在获取章节内容: {item_ids}")
        result = api.get_chapter_content(item_ids)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("获取章节内容失败")
            
    elif command == "download_full":
        if len(sys.argv) < 4:
            print("请提供书籍ID和章节ID列表")
            return
            
        book_id = sys.argv[2]
        item_ids = sys.argv[3]
        print(f"正在下载整本小说: {book_id}")
        result = api.download_full_novel(book_id, item_ids)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("下载整本小说失败")
            
    else:
        print(f"未知命令: {command}")
        print("支持的命令: search, novel_info, book_details, chapter_content, download_full")


# 当脚本被直接运行时执行主函数
if __name__ == "__main__":
    main()