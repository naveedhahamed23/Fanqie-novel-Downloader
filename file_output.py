# -*- coding: utf-8 -*-
"""
文件输出模块
处理TXT和EPUB文件的生成和保存
"""

import os
import time
from ebooklib import epub
import requests
from io import BytesIO

# 添加HEIC支持
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # 静默失败，不影响主要功能


class FileOutputManager:
    """文件输出管理器"""
    
    def __init__(self, logger=None):
        self.logger = logger
    
    def log(self, message):
        """日志输出"""
        if self.logger:
            self.logger(message)
        else:
            print(message)
    
    def save_as_txt(self, filepath, book_data, chapters, chapter_results):
        """保存为TXT文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入书籍信息
                f.write(f"书名: {book_data.get('name', '未知书名')}\n")
                f.write(f"作者: {book_data.get('author', '未知作者')}\n")
                f.write(f"简介: {book_data.get('description', '无简介')}\n")
                f.write("=" * 50 + "\n\n")
                
                # 写入章节内容
                for idx in range(len(chapters)):
                    if idx in chapter_results:
                        result = chapter_results[idx]
                        # 优先使用API返回的标题，避免与基础标题重复
                        title = (result.get("api_title") or result.get("base_title") or "").strip()
                        f.write(f'{title}\n')
                        f.write(result['content'] + '\n\n')
            
            self.log(f"TXT文件保存成功: {filepath}")
            return True
        except Exception as e:
            self.log(f"保存TXT文件失败: {str(e)}")
            return False
    
    def save_as_epub(self, filepath, book_data, chapters, chapter_results):
        """保存为EPUB文件"""
        try:
            book = self.create_epub_book(book_data, chapters, chapter_results)
            epub.write_epub(filepath, book, {})
            self.log(f"EPUB文件保存成功: {filepath}")
            return True
        except Exception as e:
            self.log(f"保存EPUB文件失败: {str(e)}")
            return False
    
    def create_epub_book(self, book_data, chapters, chapter_results):
        """创建EPUB书籍对象"""
        book = epub.EpubBook()
        
        # 设置书籍元数据
        book.set_identifier(f'book_{book_data.get("name", "unknown")}_{int(time.time())}')
        book.set_title(book_data.get('name', '未知书名'))
        book.set_language('zh-CN')
        book.add_author(book_data.get('author', '未知作者'))
        book.add_metadata('DC', 'description', book_data.get('description', '无简介'))
        
        # 封面（如果提供了URL）
        for key in ("thumb_url", "expand_thumb_url", "audio_thumb_url_hd"):
            cover_url = book_data.get(key)
            if cover_url and self._add_epub_cover(book, cover_url):
                break
        
        book.toc = []
        spine = ['nav']
        
        # 添加章节
        for idx in range(len(chapters)):
            if idx in chapter_results:
                result = chapter_results[idx]
                # 优先使用API返回的标题，避免重复
                title = (result.get("api_title") or result.get("base_title") or "").strip()
                
                chapter = epub.EpubHtml(
                    title=title,
                    file_name=f'chap_{idx}.xhtml',
                    lang='zh-CN'
                )
                
                content = result['content'].replace('\n', '<br/>')
                chapter.content = f'<h1>{title}</h1><p>{content}</p>'.encode('utf-8')
                
                book.add_item(chapter)
                book.toc.append(chapter)
                spine.append(chapter)
        
        # 添加导航
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine
        
        return book
    
    def create_epub_with_enhanced_info(self, filepath, enhanced_info, chapters, chapter_results):
        """使用增强信息创建EPUB文件"""
        try:
            book = epub.EpubBook()
            
            # 设置书籍元数据
            book.set_identifier(f'book_{enhanced_info.get("book_id", "unknown")}_{int(time.time())}')
            book.set_title(enhanced_info.get('book_name', '未知书名'))
            book.set_language('zh-CN')
            book.add_author(enhanced_info.get('author', '未知作者'))
            book.add_metadata('DC', 'description', enhanced_info.get('abstract', '无简介'))
            
            # 添加更多元数据
            if enhanced_info.get('category'):
                book.add_metadata('DC', 'subject', enhanced_info['category'])
            if enhanced_info.get('tags'):
                book.add_metadata('DC', 'subject', enhanced_info['tags'])
            if enhanced_info.get('creation_status') == '0':
                book.add_metadata('DC', 'type', '完结')
            else:
                book.add_metadata('DC', 'type', '连载中')
            
            # 封面（如果提供了URL）
            for key in ("thumb_url", "expand_thumb_url", "audio_thumb_url_hd"):
                cover_url = enhanced_info.get(key)
                if cover_url and self._add_epub_cover(book, cover_url):
                    break
            
            book.toc = []
            spine = ['nav']
            
            # 添加书籍信息页
            info_chapter = epub.EpubHtml(
                title='书籍信息',
                file_name='book_info.xhtml',
                lang='zh-CN'
            )
            
            info_content = f"""
            <h1>书籍信息</h1>
            <p><strong>书名:</strong> {enhanced_info.get('book_name', '未知书名')}</p>
            <p><strong>作者:</strong> {enhanced_info.get('author', '未知作者')}</p>
            <p><strong>分类:</strong> {enhanced_info.get('category', '未知分类')}</p>
            <p><strong>标签:</strong> {enhanced_info.get('tags', '无标签')}</p>
            <p><strong>评分:</strong> {enhanced_info.get('score', '0')}</p>
            <p><strong>字数:</strong> {enhanced_info.get('word_number', '0')}</p>
            <p><strong>章节数:</strong> {enhanced_info.get('serial_count', '0')}</p>
            <p><strong>状态:</strong> {'完结' if enhanced_info.get('creation_status') == '0' else '连载中'}</p>
            <p><strong>阅读量:</strong> {enhanced_info.get('read_count', '0')}</p>
            <p><strong>简介:</strong></p>
            <p>{enhanced_info.get('abstract', '无简介')}</p>
            """
            
            info_chapter.content = info_content.encode('utf-8')
            book.add_item(info_chapter)
            book.toc.append(info_chapter)
            spine.append(info_chapter)
            
            # 添加章节内容
            for idx in range(len(chapters)):
                if idx in chapter_results:
                    result = chapter_results[idx]
                    # 优先使用API返回的标题，避免重复
                    title = (result.get("api_title") or result.get("base_title") or "").strip()
                    
                    chapter = epub.EpubHtml(
                        title=title,
                        file_name=f'chap_{idx}.xhtml',
                        lang='zh-CN'
                    )
                    
                    content = result['content'].replace('\n', '<br/>')
                    chapter.content = f'<h1>{title}</h1><p>{content}</p>'.encode('utf-8')
                    
                    book.add_item(chapter)
                    book.toc.append(chapter)
                    spine.append(chapter)
            
            # 添加导航
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            book.spine = spine
            
            # 保存文件
            epub.write_epub(filepath, book, {})
            self.log(f"增强EPUB文件保存成功: {filepath}")
            return True
            
        except Exception as e:
            self.log(f"保存增强EPUB文件失败: {str(e)}")
            return False
    
    def append_chapter_to_txt(self, filepath, chapter_title, chapter_content):
        """追加章节到TXT文件"""
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f'{chapter_title}\n')
                f.write(chapter_content + '\n\n')
            return True
        except Exception as e:
            self.log(f"追加章节到TXT文件失败: {str(e)}")
            return False
    
    def create_directory(self, path):
        """创建目录"""
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            self.log(f"创建目录失败: {str(e)}")
            return False
    
    def _add_epub_cover(self, book, cover_url: str) -> bool:
        """下载并设置EPUB封面"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://fanqienovel.com/'
            }
            resp = requests.get(cover_url, headers=headers, timeout=10)
            resp.raise_for_status()
            content_type = resp.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return False

            raw_bytes = resp.content
            ext = 'jpg'

            # 优先转换为JPEG，提升兼容性
            need_convert = ('heic' in content_type.lower()) or ('webp' in content_type.lower())
            if not need_convert and ('jpeg' in content_type.lower() or 'jpg' in content_type.lower()):
                ext = 'jpg'
            elif not need_convert and 'png' in content_type.lower():
                ext = 'png'
            else:
                need_convert = True

            if need_convert:
                try:
                    # 尝试用Pillow进行转换
                    try:
                        from PIL import Image
                        try:
                            import pillow_heif
                            pillow_heif.register_heif_opener()
                        except Exception:
                            pass
                        img = Image.open(BytesIO(raw_bytes))
                        if img.mode not in ("RGB", "L"):
                            img = img.convert("RGB")
                        buf = BytesIO()
                        img.save(buf, format='JPEG', quality=85)
                        raw_bytes = buf.getvalue()
                        ext = 'jpg'
                    except Exception:
                        # 转换失败则回退原图（尽管可能兼容性差）
                        ext = 'jpg' if 'jpeg' in content_type.lower() or 'jpg' in content_type.lower() else ('png' if 'png' in content_type.lower() else 'jpg')
                except Exception:
                    pass

            book.set_cover(f'cover.{ext}', raw_bytes)
            return True
        except Exception as e:
            self.log(f"添加封面失败: {e}")
            return False