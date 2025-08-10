#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
封面下载测试脚本
用于验证Pillow库和图片下载功能是否正常
"""

import sys
import requests
from io import BytesIO

def test_pil_import():
    """测试PIL导入"""
    print("=== 测试PIL导入 ===")
    try:
        import PIL
        print(f"PIL版本: {PIL.__version__}")
        
        from PIL import Image, ImageTk, ImageDraw, ImageFile
        print("成功导入: Image, ImageTk, ImageDraw, ImageFile")
        
        # 测试图片插件
        import PIL.JpegImagePlugin
        import PIL.PngImagePlugin
        import PIL.GifImagePlugin
        print("成功导入图片插件: JPEG, PNG, GIF")
        
        return True
    except ImportError as e:
        print(f"PIL导入失败: {e}")
        return False

def test_image_download():
    """测试图片下载和处理"""
    print("\n=== 测试图片下载 ===")
    
    # 使用httpbin提供的测试图片
    test_urls = [
        "https://httpbin.org/image/jpeg",
        "https://httpbin.org/image/png",
        "https://picsum.photos/200/300.jpg"
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n测试 {i}/{len(test_urls)}: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            print(f"下载成功，大小: {len(response.content)} bytes")
            print(f"Content-Type: {response.headers.get('content-type')}")
            
            # 测试PIL处理
            from PIL import Image
            img = Image.open(BytesIO(response.content))
            print(f"图片信息: {img.format}, {img.size}, {img.mode}")
            
            # 测试调整大小
            resized = img.resize((120, 160))
            print(f"调整大小成功: {resized.size}")
            
            return True
            
        except Exception as e:
            print(f"测试失败: {e}")
            continue
    
    return False

def test_tkinter_image():
    """测试Tkinter图片功能"""
    print("\n=== 测试Tkinter图片功能 ===")
    
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
        
        # 创建一个简单的测试图片
        img = Image.new('RGB', (100, 100), color='red')
        photo = ImageTk.PhotoImage(img)
        print(f"ImageTk.PhotoImage创建成功: {type(photo)}")
        
        return True
        
    except Exception as e:
        print(f"Tkinter图片测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("番茄小说下载器 - 封面功能测试")
    print("=" * 50)
    
    results = []
    
    # 测试PIL导入
    results.append(("PIL导入", test_pil_import()))
    
    # 测试图片下载
    results.append(("图片下载", test_image_download()))
    
    # 测试Tkinter图片
    results.append(("Tkinter图片", test_tkinter_image()))
    
    # 输出结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有测试通过！封面功能应该可以正常工作。")
        return 0
    else:
        print("\n⚠️  部分测试失败，封面功能可能无法正常工作。")
        return 1

if __name__ == "__main__":
    sys.exit(main())