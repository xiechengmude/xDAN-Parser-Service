import os
import json
import argparse
import asyncio
from typing import Dict, List, Optional
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import io
import sys

# Vertex AI
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig, Image as VertexImage, SafetySetting

# PDF处理
from pdf2image import convert_from_path
from PIL import Image as PILImage
import pytesseract

def setup_vertex_ai():
    """初始化 Vertex AI"""
    try:
        project_id = "elated-bison-417808"
        location = "us-central1"
        vertexai.init(project=project_id, location=location)
        print(f"Vertex AI 初始化成功: project={project_id}, location={location}")
    except Exception as e:
        print(f"Vertex AI 初始化失败: {str(e)}")
        raise

def process_with_pdf2image(pdf_path: str, output_dir: str) -> List[Dict]:
    """
    将 PDF 转换为图片并进行处理
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
    
    Returns:
        List[Dict]: 每页的处理结果
    """
    # 创建临时目录存储图片
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # 转换PDF为图片
    images = convert_from_path(pdf_path)
    pages_content = []
    
    for i, image in enumerate(images, start=1):
        # 保存图片
        image_path = os.path.join(images_dir, f'page_{i}.png')
        image.save(image_path, 'PNG')
        
        # 获取图片尺寸
        width, height = image.size
        
        # OCR提取文本
        text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        
        # 获取详细布局信息
        layout_data = pytesseract.image_to_data(image, lang='chi_sim+eng', output_type=pytesseract.Output.DICT)
        
        # 整理OCR结果
        text_elements = []
        for j in range(len(layout_data['text'])):
            if layout_data['text'][j].strip():
                text_elements.append({
                    'text': layout_data['text'][j],
                    'confidence': layout_data['conf'][j],
                    'position': {
                        'x': layout_data['left'][j],
                        'y': layout_data['top'][j],
                        'width': layout_data['width'][j],
                        'height': layout_data['height'][j]
                    }
                })
        
        page_content = {
            'page_number': i,
            'image_path': image_path,
            'size': {'width': width, 'height': height},
            'text_elements': text_elements,
            'full_text': text
        }
        
        pages_content.append(page_content)
    
    return pages_content

async def process_single_page(model: GenerativeModel, page_num: int, image: PILImage.Image, output_dir: str, 
                            generation_config: GenerationConfig, safety_settings: List[SafetySetting]) -> Dict:
    """
    异步处理单个页面
    
    Args:
        model: Gemini 模型实例
        page_num: 页码
        image: PIL图像对象
        output_dir: 输出目录
        generation_config: 生成配置
        safety_settings: 安全设置
    
    Returns:
        Dict: 页面处理结果
    """
    print(f"\n开始处理第 {page_num} 页...")
    try:
        # 保存图片
        image_path = os.path.join(output_dir, f"page_{page_num}.png")
        image.save(image_path, format="PNG")
        print(f"第 {page_num} 页图片已保存到: {image_path}")
        
        # 将图片转换为字节流
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        print(f"第 {page_num} 页图片已转换为字节流")
        
        # 转换为 Vertex AI Image 对象
        try:
            vertex_image = VertexImage.from_bytes(img_byte_arr)
            print(f"第 {page_num} 页已转换为 Vertex AI Image 对象")
        except Exception as e:
            print(f"第 {page_num} 页转换为 Vertex AI Image 对象失败: {str(e)}")
            raise
        
        # 构建提示词
        prompt = """请识别并提取图片中的所有文本内容。要求：
1. 严格遵循原文内容，不要做任何修改和总结概括
2. 保持原文的段落和布局结构
3. 如果有表格，请保持表格的格式
4. 如果有图片，请标注[图片]位置
5. 使用markdown格式输出"""
        
        try:
            print(f"第 {page_num} 页开始调用 Gemini API...")
            # 生成响应
            responses = model.generate_content(
                [prompt, vertex_image],
                generation_config=generation_config,
                safety_settings=safety_settings,
            )
            print(f"第 {page_num} 页 Gemini API 调用成功")
            
            # 处理响应
            page_content = {
                "page_number": page_num,
                "content": responses.text,
                "image_path": image_path
            }
            print(f"第 {page_num} 页处理完成")
            return page_content
            
        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit exceeded" in error_msg:
                # 如果是速率限制错误，等待一段时间后重试
                wait_time = 65  # 增加等待时间到65秒
                print(f"第 {page_num} 页处理遇到速率限制，等待{wait_time}秒后重试...")
                await asyncio.sleep(wait_time)
                # 重试一次
                print(f"第 {page_num} 页开始重试...")
                responses = model.generate_content(
                    [prompt, vertex_image],
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )
                page_content = {
                    "page_number": page_num,
                    "content": responses.text,
                    "image_path": image_path
                }
                print(f"第 {page_num} 页重试成功")
                return page_content
            else:
                print(f"第 {page_num} 页处理失败: {str(e)}")
                raise
            
    except Exception as e:
        print(f"处理第 {page_num} 页时出错: {str(e)}")
        return {
            "page_number": page_num,
            "content": f"处理出错: {str(e)}",
            "image_path": image_path if 'image_path' in locals() else None,
            "error": str(e)
        }

async def process_with_vllm(pdf_path: str, output_dir: str, max_concurrent: int = 3) -> List[Dict]:
    """
    将 PDF 转换为图片并使用 Vertex AI Vision 进行分析
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        max_concurrent: 最大并发数
    
    Returns:
        List[Dict]: 每页的处理结果
    """
    print("\n=== 开始 VLLM 处理 ===")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    print(f"输出目录已创建: {output_dir}")
    
    # 将PDF转换为图片
    print("开始转换 PDF 为图片...")
    images = convert_from_path(pdf_path)
    total_pages = len(images)
    print(f"PDF共有 {total_pages} 页")
    
    # 初始化 Vertex AI
    print("初始化 Vertex AI...")
    setup_vertex_ai()
    
    # 初始化 Gemini Pro Vision 模型
    print("初始化 Gemini Pro Vision 模型...")
    model = GenerativeModel("gemini-1.5-pro-002")
    
    # 设置生成配置
    generation_config = GenerationConfig(
        temperature=0.1,
        top_p=1,
        top_k=32,
        max_output_tokens=2048,
    )
    print("生成配置已设置")
    
    # 设置安全设置
    safety_settings = [
        SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
        SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
        SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    ]
    print("安全设置已配置")
    
    # 创建任务列表
    tasks = []
    semaphore = asyncio.Semaphore(max_concurrent)
    print(f"并发限制设置为: {max_concurrent}")
    
    async def process_with_semaphore(page_num: int, image: PILImage.Image) -> Dict:
        async with semaphore:
            return await process_single_page(
                model, page_num, image, output_dir, 
                generation_config, safety_settings
            )
    
    # 创建所有任务
    print("创建处理任务...")
    for i, image in enumerate(images, start=1):
        task = asyncio.create_task(process_with_semaphore(i, image))
        tasks.append(task)
    print(f"已创建 {len(tasks)} 个任务")
    
    # 使用tqdm显示进度
    pages_content = []
    print("\n开始处理页面...")
    with tqdm(total=total_pages, desc="处理页面", file=sys.stdout) as pbar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            pages_content.append(result)
            pbar.update(1)
            print(f"已完成 {len(pages_content)}/{total_pages} 页")
    
    # 按页码排序结果
    pages_content.sort(key=lambda x: x['page_number'])
    print("\nVLLM 处理完成")
    
    return pages_content

def create_markdown_output(content: Dict, method: str) -> str:
    """
    生成Markdown格式的输出
    
    Args:
        content: 页面内容
        method: 处理方法 ('pdf2image' 或 'vllm')
    
    Returns:
        str: Markdown格式的内容
    """
    page_num = content.get('page_number', content.get('page_num', 0))
    markdown = f"# 第 {page_num} 页\n\n"
    
    if method == 'pdf2image':
        markdown += f"![页面图片]({content['image_path']})\n\n"
        markdown += "## 文本内容\n\n"
        for elem in content['text_elements']:
            markdown += f"{elem}\n\n"
            
    else:  # vllm
        if 'error' in content:
            markdown += f"**错误信息**\n\n{content['error']}\n\n"
        else:
            markdown += f"![页面图片]({content['image_path']})\n\n"
            markdown += "## 内容\n\n"
            markdown += content['content']
            markdown += "\n\n"
    
    return markdown

async def async_process_pdf(pdf_path: str, output_dir: str = "output", method: str = "pdf2image", max_concurrent: int = 5) -> None:
    """
    异步处理PDF文件
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录路径
        method: 处理方法 ('pdf2image' 或 'vllm')
        max_concurrent: 最大并发数
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        # 根据选择的方法处理PDF
        if method == "pdf2image":
            pages_content = process_with_pdf2image(pdf_path, output_dir)
        else:  # vllm
            pages_content = await process_with_vllm(pdf_path, output_dir, max_concurrent)
        
        # 处理每一页
        for page_content in pages_content:
            page_num = page_content['page_number']
            
            # 生成Markdown
            markdown_content = create_markdown_output(page_content, method)
            
            # 保存Markdown文件
            markdown_file = os.path.join(output_dir, f'page_{page_num}.md')
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 保存JSON文件
            json_file = os.path.join(output_dir, f'page_{page_num}.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(page_content, f, ensure_ascii=False, indent=2)
        
        print(f"处理完成。输出目录: {output_dir}")
        
    except Exception as e:
        print(f"处理PDF时出错: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='PDF文档处理工具')
    parser.add_argument('--pdf_path', default='docs/pdf/example.pdf', help='PDF文件路径')
    parser.add_argument('--output_dir', default='output', help='输出目录路径')
    parser.add_argument('--method', choices=['pdf2image', 'vllm'], 
                       default='pdf2image', help='PDF处理方法')
    parser.add_argument('--max_concurrent', type=int, default=5, 
                       help='最大并发数（仅适用于vllm方法）')
    args = parser.parse_args()
    
    # 运行异步主函数
    asyncio.run(async_process_pdf(
        args.pdf_path, 
        args.output_dir, 
        args.method,
        args.max_concurrent
    ))

if __name__ == "__main__":
    main()
